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


# sql = """
# SELECT datum FROM Ispit WHERE predmetId = 5 AND ocena = 9
# """
# query = parse_query(sql)
#
# plan = optimize_query(
#     query,
#     schema
# )
#
# print_plan(plan.root)
# print()
# print("TOTAL COST =", plan.total_cost)

def parse_sql(sql):
    from parser import parse_query

    return parse_query(sql)
def main():


    queries = [
        "SELECT ime FROM Student",
        "SELECT ime, prosek FROM Student WHERE indeks = 'RA-42-2021",
        "SELECT naziv, espb FROM Predmet WHERE espb >= 6",
        "SELECT ime, smer FROM Student WHERE ime = 'Ana'",
        "SELECT naziv FROM Predmet WHERE katedra = 'Matematika'",
        "SELECT tip, iznos FROM Stipendija WHERE tip = 'drzavna'",
        "SELECT ispitId, ocena FROM Ispit WHERE ocena = 10",
        "SELECT ime, smer FROM Student ORDER BY indeks",
        "SELECT ime FROM Student WHERE smer = 'SIIT' AND prosek >= 9.0",
        "SELECT datum FROM Ispit WHERE predmetId = 5 AND ocena = 9",
        "SELECT s.ime, s.smer, p.naziv, st.tip FROM Student s, Ispit i, Predmet p, Stipendija st WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.indeks = st.studentIndeks AND s.godinaUpisa >= 2020 AND i.ocena >= 7 AND st.iznos <= 15000"
    ]

    for i, sql in enumerate(queries, start=1):

        print("\n" + "=" * 70)
        print(f"UPIT {i}")
        print("=" * 70)

        print(sql)
        print()

        try:
            query = parse_sql(sql)

            plan = optimize_query(
                query,
                schema
            )

            # Ceo plan
            print_plan(plan.root)

            print()
            print(f"TOTAL COST = {plan.total_cost}")

        except Exception as e:
            print(f"GRESKA: {e}")


if __name__ == "__main__":
    main()
