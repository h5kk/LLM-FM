# GitHub Profile Updates

Copy-paste these into your GitHub profile settings (https://github.com/settings/profile).

## Name

Hanny Noueilaty

## Bio

Full stack engineer. .NET, cloud, LLMs. Building tools that make codebases easier to work with.

## README (profile repo)

If you create a `h5kk/h5kk` repo with a README.md, this renders on your GitHub profile page:

---

### Hey, I'm Hanny

I'm a software engineer based in Dallas with 8+ years building enterprise systems — mostly in .NET/C# across cloud platforms. Currently engineering lead at NuvemRx, previously JP Morgan Chase (Cyber Defense & Fraud) and CentiBlick (HIPAA-compliant telehealth).

I like building things that sit between code and the people working with it. Right now I'm working on [Feature Memory](https://github.com/h5kk/LLM-FM) — a documentation compiler that gives AI coding agents persistent, feature-level context so they don't have to rediscover your project from scratch every session.

**What I work with:** C#, .NET Core, Python, TypeScript, AWS, Azure, Docker, REST APIs, LLMs (OpenAI, Anthropic)

**What I care about:** developer tooling, system architecture, making large codebases less painful to navigate

---

## To apply the profile README

```bash
gh repo create h5kk --public --description "Profile README"
# then add the README.md content above to that repo
```

## To apply name + bio (requires `user` scope)

```bash
gh auth refresh -h github.com -s user
gh api -X PATCH user -f name="Hanny Noueilaty" -f bio="Full stack engineer. .NET, cloud, LLMs. Building tools that make codebases easier to work with."
```
