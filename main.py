from parser import parse_query
from statistics import *
from estimator import *
from optimizer import optimize_query, print_plan

schema = load_schema("schema/schema.json")
#
# print("Buffer:", schema.buffer_blocks)
# print()
#
# for table_name, table in schema.tables.items():
#
#     print("==============================")
#     print("TABLE:", table_name)
#
#     print("Rows:", table.row_count)
#     print("Blocks:", table.block_count)
#     print("Rows/block:", table.rows_per_block)
#
#     print("\nAttributes:")
#     for attr in table.attributes:
#         print(
#             f"  {attr.name} "
#             f"({attr.type}) "
#             f"unique={attr.unique} "
#             f"distinct={attr.distinct_values}"
#         )
#
#     print("\nIndexes:")
#     for index in table.indexes:
#         print(
#             f"  {index.name}"
#             f" {index.index_type}"
#             f" attributes={index.attributes}"
#             f" clustered={index.clustered}"
#             f" height={index.tree_height}"
#         )

# from parser import parse_query
#
# sql = """
# SELECT ime, smer, prosek
# FROM Student
# WHERE smer='RI' AND prosek>8;
# ORDER BY prosek;
# """
#
# query = parse_query(sql)
#
# print(query)
#
# for condition in query.where:
#     print(
#         condition.left,
#         condition.operator,
#         condition.right
#     )
#
# print("\nORDER BY:", query.order_by)

# from algorithms import *
#
#
# print(selection_full_scan(100))
#
# print(btree_equality(3, True))
#
# print(hash_equality())
#
# print(btree_range(3,100,10))

# student = schema.tables["Student"]
#
# attribute = student.get_attribute("ime")
#
# result = estimate_selection(
#     student,
#     attribute,
#     "="
# )
#
# print(result.output_rows)
#
# print(result.output_blocks)
#
# for alg in result.estimates:
#     print(alg.algorithm, alg.cost)

# student = schema.tables["Student"]
#
# ispit = schema.tables["Ispit"]
#
#
# student_indeks = (
#     student.get_attribute("indeks")
# )
#
#
# ispit_student = (
#     ispit.get_attribute("studentIndeks")
# )
#
#
# result = estimate_join(
#     student,
#     student_indeks,
#     ispit,
#     ispit_student,
#     schema.buffer_blocks
# )
#
#
#
# print("\n========== JOIN ==========")
#
# print(
#     "Output rows:",
#     result.output_rows
# )
#
# print(
#     "Output blocks:",
#     result.output_blocks
# )
#
#
# for e in result.estimates:
#
#     print(
#         e.algorithm,
#         "->",
#         e.cost
#     )



sql = """
SELECT *
FROM Student, Ispit
WHERE Student.indeks = Ispit.studentIndeks and Student.ime = 'Pera'
"""
query = parse_query(sql)

plan = optimize_query(
    query,
    schema
)

print_plan(plan.root)
print()
print("TOTAL COST = ", plan.total_cost )