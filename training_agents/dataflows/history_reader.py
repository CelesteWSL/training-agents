# -*- coding: utf-8 -*-
"""HistoryReader - unified historical data reading layer.

Reads daily_checkin/ and training/ directories for historical data,
providing date-window queries for downstream agents.

Date strategy: filename YYYYMMDDHHmmss slicing first, then TCX internal <Id> confirmation.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from training_agents.agents.utils.agent_states import ParsedActivity
from training_agents.dataflows.tcx_parser import parse_tcx


class HistoryReader:
    """Read historical data from daily_checkin/ and training/.

    Usage:
        reader = HistoryReader("data")
        ctx = reader.read("2024-02-26", "2024-03-21", max_hr=185)
    """

    def __init__(self, data_dir: str):
        self._daily_checkin_dir = os.path.join(data_dir, "daily_checkin")
        self._training_dir = os.path.join(data_dir, "training")

    # -- daily checkin -------------------------------------------------

    def get_daily_checkins(
        self, from_date: str, to_date: str
    ) -> List[dict]:
        """Return [{date, morning_hr}, ...] sorted by date."""
        results = []
        cursor = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")

        while cursor <= end:
            date_str = cursor.strftime("%Y-%m-%d")
            filepath = os.path.join(self._daily_checkin_dir, f"{date_str}.json")
            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    results.append({
                        "date": date_str,
                        "morning_hr": data.get("morning_hr", 0),                    })
                except (json.JSONDecodeError, IOError):
                    pass
            cursor += timedelta(days=1)

        return results

    # -- training history ----------------------------------------------

    def scan_training_files(self, from_date: str, to_date: str) -> List[str]:
        """Scan training/ directory, filter by filename date.

        File naming: {description}{YYYYMMDDHHmmss}.tcx
        Extract the last 14 chars before ".tcx" as the timestamp,
        first 8 chars = date. Sorted list of file paths returned.
        """
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        candidate_files = []
        if not os.path.isdir(self._training_dir):
            return candidate_files

        for filename in os.listdir(self._training_dir):
            if not filename.lower().endswith(".tcx"):
                continue
            stem = filename[:-4]  # drop ".tcx"
            if len(stem) < 14:
                continue
            ts = stem[-14:]  # last 14 chars = YYYYMMDDHHmmss
            try:
                file_date = datetime.strptime(ts[:8], "%Y%m%d")
            except ValueError:
                continue
            if from_dt <= file_date <= to_dt:
                candidate_files.append(os.path.join(self._training_dir, filename))

        candidate_files.sort()
        return candidate_files

    def get_training_activities(
        self, from_date: str, to_date: str, max_hr: int = None
    ) -> List[Tuple[str, ParsedActivity]]:
        """Return [(date_str, ParsedActivity), ...] sorted by date.

        Two-step filter:
        1. Filename date quick filter (scan_training_files)
        2. TCX internal start_time authoritative confirmation
        """
        candidates = self.scan_training_files(from_date, to_date)
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        results = []
        for filepath in candidates:
            try:
                activity = parse_tcx(filepath, max_hr=max_hr)
            except Exception:
                continue

            start_time = activity.get("start_time", "")
            if not start_time:
                continue

            try:
                act_date = datetime.strptime(start_time[:10], "%Y-%m-%d")
            except ValueError:
                continue

            if from_dt <= act_date <= to_dt:
                date_str = act_date.strftime("%Y-%m-%d")
                results.append((date_str, activity))

        results.sort(key=lambda x: x[0])
        return results

    # -- one-shot read ------------------------------------------------

    def read(
        self, from_date: str, to_date: str, max_hr: int = None
    ) -> dict:
        """Read daily_checkin + training in one call.

        Returns:
            {
                "from_date": str,
                "to_date": str,
                "daily_checkins": [{date, morning_hr}, ...],
                "training_sessions": [{date, activity: ParsedActivity}, ...],
            }
        """
        return {
            "from_date": from_date,
            "to_date": to_date,
            "daily_checkins": self.get_daily_checkins(from_date, to_date),
            "training_sessions": [
                {"date": d, "activity": a}
                for d, a in self.get_training_activities(from_date, to_date, max_hr)
            ],
        }