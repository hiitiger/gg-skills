# STL Containers & Algorithms

## Container Selection

```
Need ordered sequence?
|- Random access + contiguous? -> std::vector (default choice)
|- Fast push_front/back? -> std::deque
|- Stable pointers/iterators during insert? -> std::list
\- Fixed size at compile time? -> std::array

Need key-value lookup?
|- Ordered keys? -> std::map (log n)
|- Fast lookup (hash)? -> std::unordered_map (amortized O(1))
|- Multiple values per key? -> std::multimap / std::unordered_multimap
\- Just checking membership? -> std::set / std::unordered_set

Need a stack/queue/priority?
|- LIFO? -> std::stack
|- FIFO? -> std::queue
\- Priority? -> std::priority_queue

Special:
|- Flat sorted (C++23)? -> std::flat_map / std::flat_set
|- Bit flags? -> std::bitset<N>
\- Small N sorted lookup -> sorted vector + binary_search (beats map)
```

**Default to `std::vector`** -- cache-friendly, fastest for most workloads including small-N search.

### Performance comparison

```
Random access iteration:  vector >> deque >> list
Lookup by key:            unordered_map >> map (for large N)
Small N lookup:           sorted vector + binary_search >> any map
Insert at front:          deque >> vector
Pointer stability:        list / map (vector invalidates on realloc)
```

## Patterns Easy to Get Wrong

```cpp
// C++20 erase_if -- replaces the old erase-remove idiom
std::erase_if(vec, [](int x) { return x < 0; });

// try_emplace -- only constructs value if key absent (avoids wasted construction)
map.try_emplace("key", expensive_arg1, expensive_arg2);

// insert_or_assign -- always sets value (unlike [] which default-constructs first)
map.insert_or_assign("key", new_value);

// contains (C++20) -- cleaner than find() != end()
if (map.contains("key")) { /* ... */ }

// extract + insert -- move between maps without copy/alloc
auto node = source_map.extract("key");
dest_map.insert(std::move(node));
```

## Non-Obvious Algorithms

Algorithms that are often reimplemented by hand:

| Algorithm | Use Case | Why It Matters |
|-----------|----------|----------------|
| `std::partial_sort(b, b+N, e)` | Top N elements | O(n log N) vs full O(n log n) sort |
| `std::nth_element(b, b+k, e)` | Median / percentile | O(n) quickselect |
| `std::stable_partition(b, e, pred)` | Split by predicate, preserving order | Avoids manual two-pass |
| `std::lower_bound(b, e, val)` | Binary search on sorted data | O(log n) vs O(n) for `find` |
| `std::execution::par` | Parallel STL algorithms (C++17) | Drop-in parallelism for sort, for_each, etc. |

## Ranges Essentials (C++20)

Key patterns that improve over iterator-pair algorithms:

```cpp
// Projections -- sort by member without writing a comparator
std::ranges::sort(people, {}, &Person::age);
std::ranges::sort(people, std::greater{}, &Person::age);
```

**Useful views:** `filter`, `transform`, `take`, `drop`, `zip` (C++23), `enumerate` (C++23), `chunk` (C++23), `split`, `join`, `keys`, `values`.

**Prefer `std::ranges::` algorithms** over `std::` -- they accept ranges directly, support projections, and give better error messages via concepts.
