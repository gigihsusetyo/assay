# ADR-001: SQLite for Development, PostgreSQL for Production

**Status:** Accepted
**Date:** 2 October 2026

## Context

I wanted to use PostgreSQL. In the blueprint, I had already decided that Assay would use PostgreSQL for production. PostgreSQL is the right choice for production: reliable, mature, strong ecosystem.

But in Codespaces, I ran into two problems.

First, Docker network. I tried to run PostgreSQL via Docker Compose. The container ran, the health check was green. But from the Codespace host, port 5432 was not reachable. I checked the container network, it was empty. This is a Docker-in-Docker characteristic in Codespaces that I did not expect.

Second, sudo. I tried to install PostgreSQL server directly in the Codespace. But `sudo -u postgres psql` asked for a password I did not know. I tried `sudo -n`, the result was "password required". I tried `su postgres`, also failed. I spent quite a while on this.

In the end, I chose SQLite for development. Not ideal. But enough.

## Decision

Development uses SQLite. Production uses PostgreSQL.

The code uses SQLAlchemy, so switching databases is just changing the URL. No logic changes.

The default in `config.py` is SQLite. The environment variable `ASSAY_DATABASE_URL` can override it to PostgreSQL.

## Consequences

What I gain:

- Development runs without friction. No Docker network, no sudo.
- Tests are fast. SQLite in-memory.
- SQLAlchemy handles both databases the same way.

What I sacrifice:

- PostgreSQL-specific features are not tested in development. For example JSONB, or `FOR UPDATE SKIP LOCKED` that we planned for the job queue.
- Behavior differences between SQLite and PostgreSQL may appear in production.
- Docker Compose for PostgreSQL does not work yet. This is technical debt.

Plan:

- Week 3 or 4, fix the Docker Compose network. Or use a managed PostgreSQL (Supabase, Neon) for the demo.
- Add tests that run on PostgreSQL before deploying to production.

---

# ADR-001: SQLite untuk Development, PostgreSQL untuk Production

**Status:** Diterima
**Tanggal:** 2 Oktober 2026

## Konteks

Saya mau pakai PostgreSQL. Di blueprint, saya sudah putuskan bahwa Assay akan pakai PostgreSQL untuk production. PostgreSQL adalah pilihan yang tepat untuk production: reliable, mature, ekosistem kuat.

Tapi di Codespace, saya hadapi dua masalah.

Pertama, Docker network. Saya coba jalankan PostgreSQL lewat Docker Compose. Container jalan, health check hijau. Tapi dari host Codespace, port 5432 tidak bisa diakses. Saya cek network container, kosong. Ini karakteristik Docker-in-Docker di Codespaces yang tidak saya duga.

Kedua, sudo. Saya coba install PostgreSQL server langsung di Codespace. Tapi `sudo -u postgres psql` minta password yang tidak saya ketahui. Saya coba `sudo -n`, hasilnya "password required". Saya coba `su postgres`, juga gagal. Saya habiskan waktu cukup lama untuk ini.

Akhirnya saya pilih SQLite untuk development. Bukan ideal. Tapi cukup.

## Keputusan

Development pakai SQLite. Production pakai PostgreSQL.

Kode pakai SQLAlchemy, jadi ganti database cuma ganti URL. Tidak ada perubahan logic.

Default di `config.py` adalah SQLite. Environment variable `ASSAY_DATABASE_URL` bisa override ke PostgreSQL.

## Konsekuensi

Yang saya dapat:

- Development jalan tanpa hambatan. Tidak perlu Docker network, tidak perlu sudo.
- Tests cepat. SQLite in-memory.
- SQLAlchemy handle dua database dengan cara yang sama.

Yang saya korbankan:

- PostgreSQL-specific features tidak ditest di development. Misal JSONB, atau `FOR UPDATE SKIP LOCKED` yang kita rencanakan untuk job queue.
- Perbedaan perilaku antara SQLite dan PostgreSQL mungkin muncul di production.
- Docker Compose untuk PostgreSQL belum berfungsi. Ini utang teknis.

Rencana:

- Next, perbaiki Docker Compose network. Atau pakai managed PostgreSQL (Supabase, Neon) untuk demo.
- Tambah test yang jalan di PostgreSQL sebelum deploy ke production.