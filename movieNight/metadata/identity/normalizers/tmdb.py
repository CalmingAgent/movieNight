from movieNight.metadata.identity.fingerprint import register, blank, _minutes, _year, _embed, Fingerprint

@register("TMDB")
def tmdb_normalise(blob) -> Fingerprint:
    fp = blank()
    fp["imdb_id"]  = blob.get("imdb_id")
    fp["title"]    = blob.get("title")
    fp["title_emb"]= _embed(fp["title"])
    fp["runtime"]  = blob.get("runtime")
    fp["year"]     = _year(blob.get("release_date"))
    return fp