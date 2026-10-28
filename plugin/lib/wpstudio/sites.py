"""Resolve a site spec (`acme` or `acme:staging`) to its project folder and connection details."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from . import envfile, workspace

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DEFAULT_ENV = "live"
REQUIRED_FOR_SSH = ("SSH_HOST", "SSH_USER", "WP_PATH")


class SiteError(Exception):
    """A site spec that can't be used, with a message meant for the operator."""


@dataclass
class Site:
    slug: str
    env: str
    root: Path
    values: Dict[str, str] = field(default_factory=dict)

    @property
    def spec(self) -> str:
        return self.slug if self.env == DEFAULT_ENV else "%s:%s" % (self.slug, self.env)

    @property
    def project(self) -> Path:
        return workspace.projects_dir(self.root) / self.slug

    @property
    def secrets(self) -> Path:
        return workspace.secrets_dir(self.root) / self.slug

    @property
    def env_file(self) -> Path:
        return self.secrets / ("%s.env" % self.env)

    @property
    def server_secrets_file(self) -> Path:
        return self.secrets / ("%s.server.json" % self.env)

    @property
    def backups(self) -> Path:
        return self.project / "backups" / self.env

    @property
    def work(self) -> Path:
        return self.project / "work"

    @property
    def port(self) -> str:
        return self.values.get("SSH_PORT") or "22"

    def missing_for_ssh(self) -> List[str]:
        return [k for k in REQUIRED_FOR_SSH if not self.values.get(k)]


def parse_spec(spec: str):
    slug, _, env = spec.partition(":")
    env = env or DEFAULT_ENV
    for label, value in (("site name", slug), ("environment", env)):
        if not NAME_RE.match(value):
            raise SiteError(
                "%r isn't a valid %s: use lowercase letters, digits and dashes (e.g. acme or acme:staging)."
                % (value, label)
            )
    return slug, env


def resolve(spec: str, root: Path, need_connection: bool = True) -> Site:
    slug, env = parse_spec(spec)
    site = Site(slug=slug, env=env, root=root)
    if not site.project.is_dir():
        raise SiteError(
            "There's no project called %r yet. Create it with: wpsite init %s --url <site address>" % (slug, slug)
        )
    if site.env_file.is_file():
        site.values = envfile.read(site.env_file)
    if need_connection:
        if not site.env_file.is_file():
            raise SiteError(
                "No connection details for %s yet. Ask the operator to paste them into CREDENTIALS.txt, "
                "then run: wpsite secrets file %s" % (site.spec, site.spec)
            )
        missing = site.missing_for_ssh()
        if missing:
            raise SiteError(
                "%s is missing %s. Ask the operator to add them to CREDENTIALS.txt, then run: wpsite secrets file %s"
                % (site.spec, ", ".join(missing), site.spec)
            )
    return site


def list_sites(root: Path) -> List[Site]:
    found = []
    base = workspace.projects_dir(root)
    if not base.is_dir():
        return found
    store = workspace.secrets_dir(root)
    for project in sorted(p for p in base.iterdir() if p.is_dir() and NAME_RE.match(p.name)):
        secrets = store / project.name
        envs = sorted(f.stem for f in secrets.glob("*.env")) if secrets.is_dir() else []
        if not envs:
            found.append(Site(slug=project.name, env=DEFAULT_ENV, root=root))
        for env in envs:
            if NAME_RE.match(env):
                site = Site(slug=project.name, env=env, root=root)
                site.values = envfile.read(site.env_file)
                found.append(site)
    return found
