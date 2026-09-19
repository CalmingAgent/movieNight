from movie_night.metadata.identity.fingerprint import register, blank, _minutes, _year, _embed, Fingerprint

@register("IMDB")
def imdb_normalise(blob) -> Fingerprint:
    fp = blank()
    fp["imdb_id"]  = blob.get("tconst")           # tt…
    fp["title"]    = blob.get("primaryTitle")
    fp["title_emb"]= _embed(fp["title"])
    fp["runtime"]  = blob.get("runtimeMinutes")
    fp["year"]     = _year(blob.get("startYear"))
    return fp