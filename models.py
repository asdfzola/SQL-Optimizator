from dataclasses import dataclass, field


@dataclass
class Attribute:
    name: str
    type: str
    unique: bool
    distinct_values: int


@dataclass
class Index:
    name: str
    attributes: list[str]
    index_type: str  # Btree or hash
    clustered: bool
    tree_height: int | None = None


@dataclass
class Table:
    name: str
    row_count: int
    block_count: int
    rows_per_block: int
    attributes: list[Attribute] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)

    def get_attribute(self, name: str):
        for attr in self.attributes:
            if attr.name == name:
                return attr
        return None

    def get_index_for_attribute(self, attribute: str):
        return [
            idx for idx in self.indexes
            if attribute in idx.attributes
        ]


@dataclass
class Schema:
    buffer_blocks: int
    tables: dict[str, Table]


# modeli za sql upit:
@dataclass
class Condition:
    left: str
    operator: str
    right: str


@dataclass
class Query:
    select: list[str]
    from_tables: list[str]
    where: list[Condition]
    order_by: str | None


# Modeli za izvrsni plan

@dataclass
class PlanStep:
    operation: str
    algorithm: str
    cost: float
    output_rows: int


@dataclass
class ExecutionPlan:
    steps: list[PlanStep]
    total_cost: float
