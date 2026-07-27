import re
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

    def get_table(self, name: str):
        return self.tables[name]


# modeli za sql upit:
@dataclass
class Condition:
    left: str
    operator: str
    right: str

    def is_join(self) -> bool:
        """
        JOIN je kada su obe strane reference na atribute.

        Primer:
            S.id = I.id

        Nije JOIN:
            S.ocena > 9.5
            S.ime = 'Pera'
        """

        def is_attribute_reference(value: str) -> bool:
            value = value.strip()

            return bool(
                re.fullmatch(
                    r"[A-Za-z_]\w*\.[A-Za-z_]\w*",
                    value
                )
            )

        return (
            is_attribute_reference(self.left)
            and
            is_attribute_reference(self.right)
        )
    def is_selection(self):
        return not self.is_join()


@dataclass
class Query:
    select: list[str]
    from_tables: list[str]
    where: list[Condition]
    order_by: str | None
    table_aliases: dict[str, str] = field(default_factory=dict)


# Modeli za izvrsni plan

@dataclass
class PlanNode:
    operation: str
    algorithm: str
    cost: float
    output_rows: int
    output_blocks: int
    children: list
    details: str = ""
    materialization_cost: float = 0


@dataclass
class ExecutionPlan:
    root: PlanNode
    total_cost: float


@dataclass
class EstimateResult:
    output_rows: int
    output_blocks: int
    algorithm: str
    cost: float


@dataclass
class AlgorithmEstimate:
    algorithm: str
    cost: float


@dataclass
class SelectionEstimate:
    output_rows: int
    output_blocks: int
    estimates: list[AlgorithmEstimate]


@dataclass
class JoinEstimate:
    output_rows: int
    output_blocks: int
    estimates: list[AlgorithmEstimate]
