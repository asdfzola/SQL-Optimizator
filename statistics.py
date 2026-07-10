import json

from models import Schema, Table, Attribute, Index


def load_schema(file_path: str) -> Schema:
    print("Loading:", file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Number of tables in JSON:",
          len(data["schema"]["tables"]), "\n")

    buffer_blocks = data["bufferBlocks"]
    tables = {}

    for table_data in data["schema"]["tables"]:

        attributes = []

        for attr in table_data["attributes"]:
            attributes.append(
                Attribute(
                    name=attr["name"],
                    type=attr["type"],
                    unique=attr["unique"],
                    distinct_values=attr["distinctValues"]
                )
            )

        indexes = []

        for idx in table_data["indexes"]:
            indexes.append(
                Index(
                    name=idx["name"],
                    attributes=idx["attributes"],
                    index_type=idx["type"],
                    clustered=idx["clustered"],
                    tree_height=idx.get("treeHeight")
                )
            )
        table = Table(
            name=table_data["name"],
            row_count=table_data["rowCount"],
            block_count=table_data["blockCount"],
            rows_per_block=table_data["rowsPerBlock"],
            attributes=attributes,
            indexes=indexes
        )

        tables[table.name] = table

    return Schema(
        buffer_blocks=buffer_blocks,
        tables=tables
    )
