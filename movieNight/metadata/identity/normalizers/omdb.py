from movieNight.metadata.identity.fingerprint import register, blank, _minutes, _year, _embed, Fingerprint

@register("OMDB")
def omdb_normalise(blob) -> Fingerprint:
    fp = blank()
    fp["imdb_id"]  = blob.get("imdbID")
    fp["title"]    = blob.get("Title")
    fp["title_emb"]= _embed(fp["title"])
    fp["runtime"]  = _minutes(blob.get("Runtime"))
    fp["year"]     = _year(blob.get("Released") or blob.get("Year"))
    return fp