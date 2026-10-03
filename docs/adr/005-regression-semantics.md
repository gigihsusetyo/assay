# ADR-005: Regression Semantics — Relative vs Absolute

**Status:** Accepted
**Date:** 4 October 2026

## Context

When comparing a run against a baseline, we compute the change in each metric. The question is: how do we express that change?

Two options:

1. **Absolute change.** `baseline=0.80, current=0.718, delta=-0.082`. The raw difference.
2. **Relative change.** `baseline=0.80, current=0.718, delta=-10.25%`. The difference as a percentage of the baseline.

Both are valid. But they mean different things. And confusing them leads to wrong decisions.

Example:

- Baseline = 0.80, Current = 0.734. Relative delta = -8.2%. Absolute delta = -0.066.
- Baseline = 0.80, Current = 0.718. Relative delta = -10.25%. Absolute delta = -0.082.

The same absolute drop (-0.066) can be a different relative drop depending on the baseline.

## Decision

We report both. And we label them clearly.

The comparison engine computes:

- `delta_absolute`: current - baseline. Always in the same unit as the metric.
- `delta_percent`: (delta_absolute / abs(baseline)) * 100. Relative percentage.
- `threshold_type`: "relative" or "absolute". Defined in the policy.

The policy file can specify either:

```yaml
version: 1
thresholds:
  groundedness:
    value: 5.0
    type: relative    # 5% relative drop
  context_recall:
    value: 0.05
    type: absolute    # 0.05 absolute drop
```

If `type` is not specified, default is `relative`. This matches the current behavior.

The report shows:

```
Groundedness
  Baseline:  0.800
  Current:   0.734
  Change:    -0.066 absolute
             -8.2% relative
  Threshold: -5% relative
  Verdict:   FAIL
```

## Consequences

What we gain:

- No ambiguity. The user knows exactly what the number means.
- Policy can use either relative or absolute thresholds, whichever makes sense for the metric.
- Reports are more professional.

What we sacrifice:

- More complex output. More numbers to read.
- Policy format becomes more complex. Backward compatibility needs care.

## Backward Compatibility

The old policy format is still supported:

```yaml
version: 1
thresholds:
  groundedness: 5.0
```

This is interpreted as `type: relative` with `value: 5.0`. The same as before.

The new format is optional. Users can upgrade when they need it.

---

# ADR-005: Semantik Regresi — Relative vs Absolute

**Status:** Diterima
**Tanggal:** 4 Oktober 2026

## Konteks

Saat membandingkan run dengan baseline, kita menghitung perubahan setiap metric. Pertanyaannya: bagaimana kita menyatakan perubahan itu?

Dua opsi:

1. **Absolute change.** `baseline=0.80, current=0.718, delta=-0.082`. Selisih mentah.
2. **Relative change.** `baseline=0.80, current=0.718, delta=-10.25%`. Selisih sebagai persentase dari baseline.

Keduanya valid. Tapi artinya beda. Dan mencampur keduanya bisa menyebabkan keputusan yang salah.

Contoh:

- Baseline = 0.80, Current = 0.734. Relative delta = -8.2%. Absolute delta = -0.066.
- Baseline = 0.80, Current = 0.718. Relative delta = -10.25%. Absolute delta = -0.082.

Absolute drop yang sama (-0.066) bisa jadi relative drop yang berbeda tergantung baseline.

## Keputusan

Kami laporkan keduanya. Dan kami label dengan jelas.

Comparison engine menghitung:

- `delta_absolute`: current - baseline. Selalu dalam unit yang sama dengan metric.
- `delta_percent`: (delta_absolute / abs(baseline)) * 100. Persentase relative.
- `threshold_type`: "relative" atau "absolute". Didefinisikan di policy.

File policy bisa menentukan salah satu:

```yaml
version: 1
thresholds:
  groundedness:
    value: 5.0
    type: relative    # 5% relative drop
  context_recall:
    value: 0.05
    type: absolute    # 0.05 absolute drop
```

Kalau `type` tidak disebut, default-nya `relative`. Ini sesuai perilaku sekarang.

Report menampilkan:

```
Groundedness
  Baseline:  0.800
  Current:   0.734
  Change:    -0.066 absolute
             -8.2% relative
  Threshold: -5% relative
  Verdict:   FAIL
```

## Konsekuensi

Yang kami dapat:

- Tidak ada ambiguitas. User tahu persis apa arti angkanya.
- Policy bisa pakai threshold relative atau absolute, sesuai kebutuhan metric.
- Report lebih profesional.

Yang kami korbankan:

- Output lebih kompleks. Lebih banyak angka dibaca.
- Format policy lebih kompleks. Backward compatibility perlu hati-hati.

## Backward Compatibility

Format policy lama masih didukung:

```yaml
version: 1
thresholds:
  groundedness: 5.0
```

Ini diinterpretasikan sebagai `type: relative` dengan `value: 5.0`. Sama seperti sebelumnya.

Format baru opsional. User bisa upgrade kapan butuh.