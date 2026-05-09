"""Converts Amazon review JSON records into user profiles."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from shared.user_profile import ReviewRecord, UserProfile, UserProfileBuilder


class AmazonProcessor:
    def __init__(self, profile_builder: UserProfileBuilder | None = None) -> None:
        self.profile_builder = profile_builder or UserProfileBuilder(min_reviews=2)

    def load_profiles(self, file_path: str | Path) -> list[UserProfile]:
        records = self._read_jsonl(file_path)
        grouped: dict[str, list[ReviewRecord]] = defaultdict(list)

        for row in records:
            grouped[row["reviewerID"]].append(
                ReviewRecord(
                    review_id=str(row["review_id"]),
                    item_id=str(row["asin"]),
                    source="amazon",
                    rating=float(row["overall"]),
                    review_text=row["reviewText"],
                    category=row.get("category", "online retail"),
                    created_at=row.get("reviewTime"),
                    metadata={"title": row.get("summary", "Amazon review")},
                )
            )

        profiles: list[UserProfile] = []
        for user_id, reviews in grouped.items():
            profile = self.profile_builder.build(user_id=user_id, source="amazon", reviews=reviews)
            if profile:
                profiles.append(profile)
        return profiles

    def _read_jsonl(self, file_path: str | Path) -> Iterable[dict]:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)
