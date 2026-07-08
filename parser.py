import re

from models import Query, Condition


def parse_query(sql: str) -> Query:
    sql = sql.strip()
    sql = sql.replace(";", "")

    select_part = re.search(
        r"SELECT(.*?)FROM",
        sql,
        re.IGNORECASE | re.DOTALL
    ).group(1)

    from_part = re.search(
        r"FROM(.*?)(WHERE|ORDER BY|$)",
        sql,
        re.IGNORECASE | re.DOTALL
    ).group(1)

    select = [
        x.strip()
        for x in select_part.split(",")
    ]

    from_tables = [
        x.strip()
        for x in from_part.split(",")
    ]

    where_conditions = []

    where_match = re.search(
        r"WHERE(.*?)(ORDER BY|$)",
        sql,
        re.IGNORECASE | re.DOTALL
    )

    if where_match:
        where_part = where_match.group(1).strip()

        conditions = re.split(
            r"\s+AND\s+",
            where_part,
            flags=re.IGNORECASE
        )

        for condition in conditions:
            match = re.match(
                r"(.+?)(=|!=|>=|<=|>|<)(.+)",
                condition.strip()
            )
            if match:
                left = match.group(1).strip()
                operator = match.group(2)
                right = match.group(3).strip()

                where_conditions.append(
                    Condition(
                        left,
                        operator,
                        right
                    )
                )

    order_by = None

    order_match = re.search(
        r"ORDER BY\s+(.+)",
        sql,
        re.IGNORECASE
    )

    if order_match:
        order_by = order_match.group(1).strip()

    if order_by and "," in order_by:
        raise Exception("ORDER BY supports only one attribute")

    return Query(
        select=select,
        from_tables=from_tables,
        where=where_conditions,
        order_by=order_by
    )
