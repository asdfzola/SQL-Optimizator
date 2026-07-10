import math


# __________________________________
# SELECTION
# _________________________________

def selection_full_scan(blocks):
    return blocks


def btree_equality(height, clustered, data_blocks=1):
    if clustered:
        return height + 1 # sortiran u memoriji
    else:
        return height + 1 + data_blocks  # nije sortiran na disku, pa ce cost biti veci


def hash_equality(output_rows, clustered=False):
    if clustered:
        return 1 + math.ceil(output_rows / 10)

    else:
        return 1 + output_rows


def btree_range(height, leaf_blocks, blocks):
    return height + leaf_blocks + blocks


# __________________________________
# JOIN
# _________________________________

def nested_loop_join(br, nr, bs):
    return br + nr * bs


def nested_loop_join_memory(br, bs):
    return br + bs


def block_nested_loop_join(br, bs, m):
    return br + math.ceil(br / (m - 2)) * bs


def index_nested_loop_join(br, nr, height, clustered, matching_blocks=1):
    if clustered:
        lookup_cost = (height + math.ceil(matching_blocks / 10))
    else:
        lookup_cost = height + matching_blocks

    return br + nr * lookup_cost


def merged_join(br, bs, sorted=True, sort_cost=0):
    if sorted:
        return br + bs

    return sort_cost + br + bs  # optimizer ce da uradi Sort(R) Sort(S), ako nisu sortirane


def hash_join(br, bs):
    return 3 * (br + bs)


def projection(blocks):
    return blocks


def projection_with_duplicates(blocks, sort_cost):
    return blocks + sort_cost


# ------------------------------
# SORT
# ------------------------------

def external_merge_sort(br, m):
    if br <= m:
        return 2 * br

    # formula sa interneta
    initial_runs = math.ceil(br / m)
    passes = math.ceil(math.log(initial_runs, m - 1))

    return 2 * br * (1 + passes)

    # formula sa pdf sa predavanja
    # initial_runs = math.ceil(br / m)
    # help = math.floor(m / bb)
    # passes = math.ceil(math.log(initial_runs, help - 1))
    #
    # return br * (2 * passes + 1)
