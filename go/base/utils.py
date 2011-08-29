def padded_queryset(queryset, size=6, padding=None):
    nr_of_results = queryset.count()
    if nr_of_results >= size:
        return queryset

    filler = [padding] * (size - nr_of_results)
    results = list(queryset)
    results.extend(filler)
    return results
