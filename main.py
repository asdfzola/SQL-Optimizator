from parser import parse_query
from statistics import *
from estimator import *
from optimizer import optimize_query, print_plan

schema = load_schema("schema/schema.json")


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
        "SELECT s.ime, s.smer, p.naziv, st.tip FROM Student s, Ispit i, Predmet p, Stipendija st WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.indeks = st.studentIndeks AND s.godinaUpisa >= 2020 AND i.ocena >= 7 AND st.iznos <= 15000",
        "SELECT s.ime, i.ocena, i.datum FROM Student s, Ispit i WHERE s.indeks = i.studentIndeks AND i.ocena >= 9 ORDER BY i.datum",
        "SELECT p.naziv, i.ocena FROM Ispit i, Predmet p WHERE i.predmetId = p.predmetId AND p.katedra = 'Informatika'",
        "SELECT s.ime, st.iznos FROM Student s, Stipendija st WHERE s.indeks = st.studentIndeks AND st.iznos > 20000",
        "SELECT s.ime, p.naziv, i.ocena FROM Student s, Ispit i, Predmet p WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.smer = 'RN' AND i.ocena >= 8",
        "SELECT s.ime, p.naziv FROM Student s, Ispit i, Predmet p WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND p.espb >= 6 ORDER BY p.naziv",
        "SELECT s.ime, st.tip FROM Student s, Ispit i, Stipendija st WHERE s.indeks = i.studentIndeks AND s.indeks = st.studentIndeks AND i.ocena = 10",
        "SELECT s.ime, p.naziv, st.iznos FROM Student s, Ispit i, Predmet p, Stipendija st WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.indeks = st.studentIndeks AND st.tip = 'gradska'",
        "SELECT s.ime, p.naziv, st.iznos FROM Student s, Ispit i, Predmet p, Stipendija st WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.indeks = st.studentIndeks AND p.espb >= 6 AND s.prosek >= 8.5 ORDER BY s.ime",
        "SELECT s.ime, s.smer, p.naziv, st.tip FROM Student s, Ispit i, Predmet p, Stipendija st WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND s.indeks = st.studentIndeks AND s.godinaUpisa >= 2020 AND i.ocena >= 7 AND st.iznos <= 15000",
        "SELECT s.ime, p.naziv FROM Student s, Ispit i, Predmet p WHERE s.indeks = i.studentIndeks AND i.predmetId = p.predmetId AND i.ocena >= 8 ORDER BY s.ime"
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
