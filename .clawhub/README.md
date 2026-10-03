# ClawHub distribution

This directory is the source of truth for publishing this repository's product skills to ClawHub. `publish.json` enumerates every product skill; no workflow may infer publishable entries by scanning directories.

## Rights

On 2026-10-03, the zenstory organization creator recorded that they created the organization and that the other contributors agreed to MIT-0 distribution of these skill packages. The source repository license is unchanged. The packager must preserve applicable notices and, when a skill does not carry its own license file, copy the repository-root `LICENSE` into the package as `LICENSE`. This record authorizes packaging; it does not authorize changing an existing ClawHub owner or creating a replacement identity for an existing entry.

## Package closure and fingerprint

Each `include` pattern is relative to that skill's `path`. Paths may not escape the skill directory, follow symlinks, or pull repository-development scripts into a runtime package. `**/*` intentionally includes the skill-local `SKILL.md`, references, scripts, agents, templates, and other runtime assets.

The canonical packager adds the root license only when needed. Cross-platform integrity uses the exact `{path, sha256, size}` file inventory with original bytes. ClawHub v0.23.3 computes its fingerprint using JavaScript `path.localeCompare()` sorting, so the pinned CLI dry run and write must run on the same runtime. Neither digest includes the publish mode. `packageDigest` locks path-sorted canonical JSON `{path, sha256, size}` records; update the explicit version and regenerate the lock with the pinned central `clawhub_release.py lock` command whenever package bytes or exact companion versions change.

## Cold start and normal operation

`bootstrapSha` pins the first authorized source snapshot so the initial upload does not wait for a future release. Manual bootstrap, stable releases, and the 12-hour reconciliation schedule all call the same central writer. Identical owner/slug/version/fingerprint tuples are no-ops; the workflow must fail rather than overwrite a different fingerprint at the same version.

New entries begin at the explicit `1.0.0` semver baseline; known existing entries retain an owner-qualified current/target version instead of being reset. Before the first write, the organization-level dry run reconciles every version with the existing ClawHub identity. `publisher: worldwonderer` is also subject to owner-qualified resolution before a write.

`supportedRuntimes` remains empty until that exact package has been exercised on the runtime; publication alone is not runtime verification. `runtimeDependsOn` records declared host/binary prerequisites but is not a verification claim.

