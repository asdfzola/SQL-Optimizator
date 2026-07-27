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

_FLIPPED_OPERATOR = {
    "=": "=",
    "!=": "!=",
    "<": ">",
    ">": "<",
    "<=": ">=",
    ">=": "<=",
}


@dataclass
class Condition:
    left: str
    operator: str
    right: str

    @staticmethod
    def _is_literal(value: str) -> bool:
        """Da li je vrednost brojevni ili string literal (a ne referenca na atribut)."""
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _is_reference(self, value: str, table_aliases: dict[str, str] | None = None) -> bool:
        value = value.strip()
        if "." not in value:
            return False
        if self._is_literal(value):
            return False
        if table_aliases is not None:
            prefix = value.split(".", 1)[0]
            return prefix in table_aliases
        return True

    def is_join(self, table_aliases: dict[str, str] | None = None) -> bool:
        """
        Uslov je JOIN samo ako su OBE strane prave table.atribut reference
        (ne brojevni/string literal koji slucajno sadrzi tacku, npr. '1000.50').
        Ako je dostupna table_aliases mapa (iz Query), dodatno se proverava
        da prefiks pre tacke zaista jeste poznat alias.
        """
        return self._is_reference(self.left, table_aliases) and self._is_reference(self.right, table_aliases)

    def is_selection(self, table_aliases: dict[str, str] | None = None) -> bool:
        return not self.is_join(table_aliases)

    def normalized(self, table_aliases: dict[str, str] | None = None) -> "Condition":
        """
        Za SELEKCIONE uslove: vraca uslov kod koga je atributska referenca
        UVEK na levoj strani (npr. '5 = R.ocena' -> 'R.ocena = 5',
        '5 < R.plata' -> 'R.plata > 5'). Operator se obrne kad se strane zamene.
        Join uslovi i uslovi koji vec imaju referencu levo ostaju nepromenjeni.
        """
        left_is_ref = self._is_reference(self.left, table_aliases)
        right_is_ref = self._is_reference(self.right, table_aliases)

        if left_is_ref or not right_is_ref:
            return self

        flipped_operator = _FLIPPED_OPERATOR.get(self.operator, self.operator)
        return Condition(left=self.right, operator=flipped_operator, right=self.left)


@dataclass
class Query:
    select: list[str]
    from_tables: list[str]
    where: list[Condition]
    order_by: str | None
    table_aliases: dict[str, str] = field(default_factory=dict)  # alias -> pravo ime tabele


# Modeli za izvrsni plan

@dataclass
class PlanStep:
    operation: str
    algorithm: str
    cost: float
    output_rows: int

@dataclass
class PlanNode:
    operation: str
    algorithm: str
    cost: float
    output_rows: int
    output_blocks: int
    children: list
    details: str = ""
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





