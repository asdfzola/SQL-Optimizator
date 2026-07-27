import math


# __________________________________
# SELECTION
# _________________________________

def selection_full_scan(blocks):
    return blocks


def linear_search(blocks, attribute_unique=False, operator="="):
    if operator == "=" and attribute_unique:
        return math.ceil(blocks / 2)

    return blocks


def btree_equality(height, clustered, output_rows, output_blocks, unique=False):
    if unique:
        return height + 1

    if clustered:
        return height + output_blocks

    return height + output_rows


def btree_range(height, clustered, output_rows, output_blocks):
    if clustered:
        return height + output_blocks

    return height + output_rows


def hash_equality(output_rows, output_blocks, clustered, unique=False):
    """
    ~1.2 predstavlja prosecnu cenu pristupa hash kanti (obicno 1 I/O,
    povremeno vise zbog overflow lanaca). Dodaje se u SVIM slucajevima,
    ne samo za unique - u prethodnoj verziji je nedostajala za
    ne-jedinstvene atribute, sto je bilo nedosledno sa formulom
    koju calculate_index_lookup_cost_for_join vec koristi za JOIN.
    """
    if unique:
        return 1.2

    if clustered:
        return 1.2 + output_blocks

    return 1.2 + output_rows


# __________________________________
# JOIN
# _________________________________

def nested_loop_join(br, nr, bs):
    """
    br- broj blokova spoljne relacije (OUTER BLOCKS)
    nr- broj redova spoljne relacije (OUTER ROWS)
    bs - broj blokova unutrasnje relacije (INNER BLOCKS)
    """
    return br + nr * bs


def block_nested_loop_join(br, bs, m):
    if m <= 2:
        return float("inf")
    return br + math.ceil(br / (m - 2)) * bs


def index_nested_loop_join(br, nr, lookup_cost):
    return br + nr * lookup_cost


def merge_join(
        left_blocks,
        right_blocks,
        left_sort_cost,
        right_sort_cost
):
    """
    Merge Join kada ulazi nisu prethodno sortirani:

    """

    return (
            left_sort_cost
            + right_sort_cost
            + left_blocks
            + right_blocks
    )


def merge_join_sorted(left_blocks, right_blocks):
    """
    Merge Join kada su oba ulaza već sortirana.
    """

    return left_blocks + right_blocks


def hash_join(br, bs, buffer_blocks):
    if min(br, bs) <= buffer_blocks:
        return br + bs
    return 3 * (br + bs)


# ------------------------------
# SORT
# ------------------------------

def external_merge_sort(br, m):
    if br <= m:
        return br

    # formula sa interneta
    initial_runs = math.ceil(br / m)
    merge_in = m - 1
    passes = 0

    for _ in range(10 ** 9):
        if initial_runs <= 1:
            break

        initial_runs = math.ceil(initial_runs / merge_in)
        passes += 1

    return br * (2 * passes + 1)

    # formula sa pdf sa predavanja
    # initial_runs = math.ceil(br / m)
    # help = math.floor(m / bb)
    # passes = math.ceil(math.log(initial_runs, help - 1))
    #
    # return br * (2 * passes + 1)
