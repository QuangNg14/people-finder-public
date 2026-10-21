"""GitHub: users, org members, and profile enrichment. Official REST API only."""

from __future__ import annotations

from datetime import date
from typing import Any

from core.cache import TTL_PROFILE
from core.http import SourceError
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.github.com"
MAX_ENRICH = 10  # one general request per person; keeps unauthenticated runs inside 60/hour


@register
class GitHub(BaseSource):
    name = SourceName.GITHUB
    requires_key = False
    key_env = ("GITHUB_TOKEN",)
    returns = "GitHub user profiles (name, company, location, blog, X handle) and repo owners"

    def missing_keys(self) -> list[str]:
        return []  # works unauthenticated at 10 search req/min; the token only raises limits

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = self.key()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _search(self, q: SourceQuery) -> list[Hit]:
        if q.person:
            return self._people(q)
        return self._discover(q)

    def _people(self, q: SourceQuery) -> list[Hit]:
        assert q.person is not None
        terms = [q.person.lstrip("@")]
        if q.location:
            terms.append(f'location:"{q.location}"')
        query = " ".join(terms)
        logins = self._search_users(query, q.limit)
        if q.org:
            members = set(self._org_members(q.org))
            # Org members first: a stronger corroborating signal than a name match.
            logins = [u for u in logins if u in members] + [u for u in logins if u not in members]
        return [h for h in (self._profile(u, query) for u in logins[:MAX_ENRICH]) if h]

    def _discover(self, q: SourceQuery) -> list[Hit]:
        assert q.description is not None
        hits: list[Hit] = []
        enriched: set[str] = set()
        user_query = q.description + (f' location:"{q.location}"' if q.location else "")
        for login in self._search_users(user_query, min(q.limit, MAX_ENRICH)):
            hit = self._profile(login, user_query)
            if hit:
                hits.append(hit)
                enriched.add(login)
        repo_query = f"{q.description} in:name,description,topics"
        data = self.http.get(
            self.name,
            f"{API}/search/repositories",
            params={"q": repo_query, "sort": "stars", "per_page": min(q.limit, 30)},
            headers=self._headers(),
        ).json()
        for repo in data.get("items", []):
            owner: dict[str, Any] = repo.get("owner") or {}
            if owner.get("type") != "User":
                continue
            hits.append(
                make_hit(
                    self.name,
                    "repo",
                    repo["html_url"],
                    repo.get("full_name", ""),
                    repo.get("description") or "",
                    {
                        "owner_login": owner.get("login"),
                        "stars": repo.get("stargazers_count"),
                        "topics": repo.get("topics"),
                        "language": repo.get("language"),
                    },
                    repo_query,
                )
            )
        # Repo owners become candidates too; their repos attach to them as evidence.
        owners = [h.payload["owner_login"] for h in hits if h.kind == "repo"]
        for login in dict.fromkeys(owners):
            if len(enriched) >= MAX_ENRICH:
                break
            if login in enriched:
                continue
            hit = self._profile(str(login), repo_query)
            if hit:
                hits.append(hit)
                enriched.add(str(login))
        return hits

    def _search_users(self, query: str, limit: int) -> list[str]:
        data = self.http.get(
            self.name,
            f"{API}/search/users",
            params={"q": query, "per_page": min(limit, 30)},
            headers=self._headers(),
        ).json()
        return [item["login"] for item in data.get("items", []) if item.get("type") == "User"]

    def _org_members(self, org: str) -> list[str]:
        slug = org.strip().lstrip("@")
        if not slug or " " in slug:
            return []  # free-text org names ("University of Toronto") are not GitHub org slugs
        try:
            data = self.http.get(
                self.name,
                f"{API}/orgs/{slug}/members",
                params={"per_page": 100},
                headers=self._headers(),
                ttl=TTL_PROFILE,
            ).json()
        except SourceError:
            return []  # unknown org: rank by name only rather than failing the source
        return [m["login"] for m in data] if isinstance(data, list) else []

    def _profile(self, login: str, provenance: str) -> Hit | None:
        u = self.http.get(
            self.name, f"{API}/users/{login}", headers=self._headers(), ttl=TTL_PROFILE
        ).json()
        if not u.get("html_url"):
            return None
        company = (u.get("company") or "").strip()
        return make_hit(
            self.name,
            "profile",
            u["html_url"],
            u.get("name") or u["login"],
            u.get("bio") or "",
            {
                "login": u["login"],
                "name": u.get("name"),
                "company": company.lstrip("@") if company else None,
                "location": u.get("location"),
                "blog": u.get("blog"),
                "twitter_username": u.get("twitter_username"),
                "bio": u.get("bio"),
                "public_repos": u.get("public_repos"),
                "followers": u.get("followers"),
                "created_at": u.get("created_at"),
            },
            provenance,
        )

    def _fetch(self, ref: str) -> Hit | None:
        return self._profile(ref.strip().lstrip("@"), f"users/{ref}")

    def user_repos(self, login: str, limit: int = 10) -> list[Hit]:
        """Public non-fork repos owned by the user, newest created first. May raise."""
        handle = login.strip().lstrip("@")
        data = self.http.get(
            self.name,
            f"{API}/users/{handle}/repos",
            params={"sort": "created", "direction": "desc", "per_page": min(limit, 100)},
            headers=self._headers(),
        ).json()
        if not isinstance(data, list):
            return []
        return [
            make_hit(
                self.name,
                "repo",
                r["html_url"],
                r.get("full_name") or r.get("name") or "",
                r.get("description") or "",
                {
                    "published": r.get("created_at"),
                    "pushed_at": r.get("pushed_at"),
                    "owner_login": (r.get("owner") or {}).get("login"),
                    "stars": r.get("stargazers_count"),
                    "language": r.get("language"),
                },
                f"repos of {handle}",
            )
            for r in data
            if r.get("html_url") and not r.get("fork")
        ]

    def user_releases(
        self, login: str, since: date | None = None, repo_limit: int = 5, per_repo: int = 3
    ) -> list[Hit]:
        """Releases from the user's most recently pushed own repos, dated by `published_at`.

        A release in a years-old repo still appears, because repos are chosen by last push, not
        by creation date. May raise.
        """
        handle = login.strip().lstrip("@")
        repos = self.http.get(
            self.name,
            f"{API}/users/{handle}/repos",
            params={"sort": "pushed", "direction": "desc", "per_page": min(repo_limit, 30)},
            headers=self._headers(),
        ).json()
        if not isinstance(repos, list):
            return []
        hits: list[Hit] = []
        for repo in repos:
            if repo.get("fork") or not repo.get("full_name"):
                continue
            pushed = str(repo.get("pushed_at") or "")[:10]
            if since and pushed and pushed < since.isoformat():
                continue  # no push since the cutoff means no release since it either
            releases = self.http.get(
                self.name,
                f"{API}/repos/{repo['full_name']}/releases",
                params={"per_page": per_repo},
                headers=self._headers(),
            ).json()
            for rel in releases if isinstance(releases, list) else []:
                if rel.get("draft") or not rel.get("html_url"):
                    continue
                label = rel.get("name") or rel.get("tag_name") or ""
                hits.append(
                    make_hit(
                        self.name,
                        "release",
                        rel["html_url"],
                        f"{repo['full_name']} {label}".strip(),
                        rel.get("body") or "",
                        {
                            "published": rel.get("published_at"),
                            "owner_login": handle,
                            "tag": rel.get("tag_name"),
                            "prerelease": rel.get("prerelease") or None,
                        },
                        f"releases of {handle}",
                    )
                )
        return hits
