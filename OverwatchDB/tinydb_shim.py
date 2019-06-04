from tinydb import TinyDB, Query
from .db_shim import AbstractDBHandler
from .utils import (
    TODAY,
    OWRELEASEDATE,
    OverwatchHeroes
)
from ._quicksort import qsort
import logging
import json
import jsonschema
import datetime
from typing import Optional

logging.basicConfig(
    format="[%(asctime)s] - %(levelname)s/%(name)s: %(message)s",
    level=logging.DEBUG
)
LOG = logging.getLogger(__name__)


def print_dates(entries: dict):
    for entry in entries:
        print(entry["video_date"])
    print("-"*10)


class TinyDBHandler(AbstractDBHandler):
    def __init__(
        self, *, db: str="video-metadata.json",
        schemafile: str="db_form.json"
    ):
        self._db_name = db
        self._db = None
        with open(schemafile) as fd:
            self._schema = json.loads(fd.read())

    def __enter__(self):
        self.open()
        return self

    def __exit__(self):
        self.close()

    def open(self):
        self._db = TinyDB(self._db_name)

    def close(self):
        self._db.close()

    def _url_check(self, url: str) -> bool:
        if self._db is not None:
            return self._db.contains(Query().video_url == url)
        else:
            raise ValueError("No database found")
    
    def _validate_date(self, date_prototype: str) -> str:
        # Expected prototype ISO 8061 (yyyy-mm-dd)
        candidate = datetime.date.fromisoformat(date_prototype)
        if candidate > TODAY:
            raise ValueError(f"{date_prototype} is after today")
        if candidate < OWRELEASEDATE:
            raise ValueError(f"{date_prototype} is before Overwatch release day")
        return candidate.isoformat()

    def _parse_tags(self, tags: str) -> list:
        if tags is None:
            return []
        return [tag for tag in tags.split() if tag.startswith("#")]
    
    def insert(self, data: dict) -> tuple:
        try:
            LOG.debug(data)
            jsonschema.validate(data, self._schema)
            data["video_date"] = self._validate_date(data["video_date"])
            data["tags"] = self._parse_tags(data["tags"])
            if data["video_title"] is None:
                data["video_title"] = f"{data['video_date'].replace('-','')}_{data['hero']}"
            if data["type"] is None:
                data["type"] = "highlight"
            if self._url_check(data["video_url"]) is True:
                raise ValueError(f"{data['video_url']} is already tracked")
            if self._db is not None:
                self._db.insert(data)
            else:
                raise ValueError("No database found")
            return '', 200
        except ValueError as e:
            LOG.warning(str(e))
            return f"Error: {e!s}", 400
        except jsonschema.ValidationError as e:
            LOG.warning(str(e))
            return f"Invalid JSON: {e!s}", 400
        except Exception as e:
            LOG.warning(str(e))
            return str(e), 500

    def _date_query_builder(
        self, start_date: datetime.date, *,
        end_date: Optional[datetime.date]=TODAY
    ):
        def date_filter(
            video_date: str, start_date: datetime.date, end_date: datetime.date
        ):
            test_date = datetime.date.fromisoformat(video_date)
            return start_date <= test_date <= end_date
        return Query().video_date.test(date_filter, start_date, end_date)

    def fetch_by_dates(
        self, start_date: datetime.date, *,
        end_date: Optional[datetime.date]=TODAY
    ) -> list:
        result = self._db.search(self._date_query_builder(start_date, end_date))
        qsort(result, 0, len(result)-1)
        return result

    def _hero_query_builder(self, hero: OverwatchHeroes):
        return (Query().hero == str(hero))

    def fetch_by_hero_name(self, hero: OverwatchHeroes) -> list:
        result = self._db.search(self._hero_query_builder(hero))
        qsort(result, 0, len(result)-1)
        return result

    def _tag_query_builder(self, tag: str):
        def tag_filter(tags: list, tag: str):
            return tag in tags
        return Query().tags.test(tag_filter, tag)

    def fetch_by_tag(self, tag: str) -> list:
        result = self._db.search(self._tag_query_builder(tag))
        qsort(result, 0, len(result)-1)
        return result

    def fetch_by_multiple(
        self, *,
        start_date: Optional[datetime.date]=None,
        end_date: Optional[datetime.date]=TODAY,
        hero_name: Optional[OverwatchHeroes]=None,
        tag: Optional[str] = None
    ) -> list:
        date_query = Query()
        hero_query = Query()
        tag_query = Query()
        if start_date is not None:
            date_query = self._date_query_builder(start_date, end_date=end_date)
        if hero_name is not None:
            hero_query = self._hero_query_builder(hero_name)
        if tag is not None:
            tag_query = self._tag_query_builder(tag)
        result = self._db.search(date_query & hero_query & tag_query)
        # print_dates(result)
        qsort(result, 0, len(result)-1)
        # print_dates(result)
        return result