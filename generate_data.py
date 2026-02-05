#!/usr/bin/env python3
"""
Esports Calendar — Data Generator

Scrapes match data from Liquipedia for configured teams and outputs
JSON data files. By default writes to public/data/ for local dev.
With --r2, uploads to Cloudflare R2 storage.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src import Match, TeamConfig
from src.cache import load_json_cache, save_json_cache
from src.notify import send_error_notification
from src.scraper import fetch_team_matches


def load_teams(path: str = "teams.json") -> list[TeamConfig]:
    """Load team configurations from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return [TeamConfig(**t) for t in data["teams"]]


def match_to_dict(m: Match) -> dict:
    """Convert a Match to a JSON-serializable dict."""
    return {
        "timestamp": m.timestamp,
        "opponent": m.opponent,
        "tournament": m.tournament,
        "url": m.url,
        "is_upcoming": m.is_upcoming,
    }


def create_r2_client():
    """Create an S3 client configured for Cloudflare R2."""
    import boto3

    account_id = os.environ["CF_ACCOUNT_ID"]
    access_key = os.environ["R2_ACCESS_KEY_ID"]
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"]

    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def upload_to_r2(s3_client, bucket: str, key: str, data: str) -> None:
    """Upload a JSON string to R2."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data.encode("utf-8"),
        ContentType="application/json",
    )


def main() -> int:
    use_r2 = "--r2" in sys.argv
    bucket_name = "esports-calendar-data"
    s3_client = None

    if use_r2:
        try:
            s3_client = create_r2_client()
            print("R2 upload enabled")
        except Exception as e:
            print(f"ERROR: Failed to create R2 client: {e}")
            return 1

    teams = load_teams()
    output_dir = Path("public/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    generated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    team_manifest: list[dict] = []
    errors: list[str] = []
    r2_uploads: list[tuple[str, str]] = []  # (key, json_str) pairs to upload

    for i, team in enumerate(teams):
        print(f"\n{team.emoji} Fetching {team.name} matches from Liquipedia...")

        # Be respectful to Liquipedia — 2 second delay between requests
        if i > 0:
            time.sleep(2)

        try:
            matches = fetch_team_matches(team)
            upcoming = [m for m in matches if m.is_upcoming]
            past = [m for m in matches if not m.is_upcoming]
            print(f"  Found {len(upcoming)} upcoming, {len(past)} past matches")

            if not upcoming and not past:
                print("  Warning: no matches found (page structure may have changed)")
                # Don't overwrite good data with empty data — use cache instead
                cached = load_json_cache(cache_dir, team.slug)
                if cached:
                    print(f"  Using cached data (has matches) instead of empty scrape")
                    key = f"{team.slug.lower()}.json"
                    out_path = output_dir / key
                    out_path.write_text(cached, encoding="utf-8")
                    r2_uploads.append((key, cached))
                    manifest_team = {
                        "name": team.name,
                        "slug": team.slug,
                        "short_name": team.short_name,
                        "emoji": team.emoji,
                        "game": team.game,
                    }
                    if team.logo_url:
                        manifest_team["logo_url"] = team.logo_url
                    team_manifest.append(manifest_team)
                    continue

            team_data = {
                "team": {
                    "name": team.name,
                    "slug": team.slug,
                    "short_name": team.short_name,
                    "emoji": team.emoji,
                    "game": team.game,
                    "liquipedia_url": team.liquipedia_url,
                },
                "matches": [match_to_dict(m) for m in matches],
                "generated_utc": generated_utc,
            }

            # Add logo_url if available
            if team.logo_url:
                team_data["team"]["logo_url"] = team.logo_url

            json_str = json.dumps(team_data, indent=2, ensure_ascii=False)

            # Save to local output
            key = f"{team.slug.lower()}.json"
            out_path = output_dir / key
            out_path.write_text(json_str, encoding="utf-8")
            print(f"  Saved {out_path}")

            # Queue for R2 upload
            r2_uploads.append((key, json_str))

            # Cache the successful result
            save_json_cache(cache_dir, team.slug, json_str)

            # Add to manifest
            manifest_team = {
                "name": team.name,
                "slug": team.slug,
                "short_name": team.short_name,
                "emoji": team.emoji,
                "game": team.game,
            }
            if team.logo_url:
                manifest_team["logo_url"] = team.logo_url
            team_manifest.append(manifest_team)

            for m in upcoming:
                dt = datetime.fromtimestamp(m.timestamp, tz=timezone.utc)
                print(f"    {dt.strftime('%Y-%m-%d %H:%M UTC')} vs {m.opponent}")

        except Exception as e:
            time.sleep(2)  # Be respectful to Liquipedia even on errors
            error_msg = f"Failed to fetch {team.name}: {e}"
            print(f"  ERROR: {error_msg}")
            errors.append(error_msg)

            # Try cache fallback
            cached = load_json_cache(cache_dir, team.slug)
            if cached:
                print(f"  Using cached data for {team.name}")
                key = f"{team.slug.lower()}.json"
                out_path = output_dir / key
                out_path.write_text(cached, encoding="utf-8")
                r2_uploads.append((key, cached))
                # Still add to manifest
                manifest_team = {
                    "name": team.name,
                    "slug": team.slug,
                    "short_name": team.short_name,
                    "emoji": team.emoji,
                    "game": team.game,
                }
                if team.logo_url:
                    manifest_team["logo_url"] = team.logo_url
                team_manifest.append(manifest_team)
            else:
                send_error_notification(
                    f"{error_msg}\n\nNo cached data available — team will be missing."
                )

    # Write team manifest
    manifest = {
        "teams": team_manifest,
        "generated_utc": generated_utc,
    }
    manifest_json = json.dumps(manifest, indent=2, ensure_ascii=False)
    manifest_path = output_dir / "teams.json"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    print(f"\nSaved {manifest_path} ({len(team_manifest)} teams)")
    r2_uploads.append(("teams.json", manifest_json))

    # Copy leagues.json into public/data/ so the frontend can fetch it
    leagues_src = Path("leagues.json")
    if leagues_src.exists():
        leagues_json = leagues_src.read_text(encoding="utf-8")
        leagues_dst = output_dir / "leagues.json"
        leagues_dst.write_text(leagues_json, encoding="utf-8")
        print(f"Copied {leagues_src} → {leagues_dst}")
        r2_uploads.append(("leagues.json", leagues_json))

    # Upload to R2 if enabled
    if use_r2 and s3_client:
        print(f"\nUploading {len(r2_uploads)} files to R2...")
        for key, data in r2_uploads:
            try:
                upload_to_r2(s3_client, bucket_name, key, data)
                print(f"  Uploaded {key}")
            except Exception as e:
                error_msg = f"Failed to upload {key} to R2: {e}"
                print(f"  ERROR: {error_msg}")
                errors.append(error_msg)
        print("R2 upload complete")

    # Summary
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for err in errors:
            print(f"  - {err}")
        send_error_notification(
            f"Data generation completed with {len(errors)} error(s):\n\n"
            + "\n".join(f"- {e}" for e in errors)
        )
        return 1

    print("\nDone — all data generated successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
