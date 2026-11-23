package app.followpoppy

/**
 * English mode, all the way: street and place names that only exist in Hebrew (the map's local name) are put in
 * English letters, so they can be read and spoken (an English voice cannot read Hebrew). A name the map knows in
 * English (OpenStreetMap's name:en, in the Mapbox street tiles around the route) is used as it is; otherwise the
 * Hebrew is spelled out in Latin letters the way Israeli street signs do (Dizengoff, Ben Yehuda, Allenby).
 */
object HebrewLatin {
    private val RUN = Regex("[\\u0590-\\u05FF][\\u0590-\\u05FF'\"׳״\\- ]*[\\u0590-\\u05FF'׳]|[\\u0590-\\u05FF]")

    fun has(s: String) = s.any { it in '֐'..'׿' }

    /** [text] with every Hebrew part replaced: by its English name from [names] (Hebrew → English) or spelled out. */
    fun english(text: String, names: Map<String, String> = emptyMap()): String {
        if (!has(text)) return text
        return RUN.replace(text) { m ->
            val run = m.value.trim()
            names[run] ?: names.entries.firstOrNull { (he, _) -> he.isNotEmpty() && (run.contains(he) || he.contains(run)) && kotlin.math.min(he.length, run.length) >= 3 }
                ?.let { (he, en) -> if (he == run) en else if (run.contains(he)) run.replace(he, "\u0000").let { spell(it).replace("\u0000", en) } else en }
                ?: spell(run)
        }.replace(Regex(" {2,}"), " ").trim()
    }

    /** Hebrew letters in Latin letters, word by word, capitalised (street-sign style). */
    fun spell(s: String): String = s.split(' ').joinToString(" ") { word -> spellWord(word).replaceFirstChar { it.uppercaseChar() } }

    private fun spellWord(w: String): String {
        val c = w.replace('״', '"').replace('׳', '\'')
        // letters → sounds, each marked consonant or vowel
        val toks = ArrayList<Pair<String, Boolean>>()            // (sound, is a vowel)
        var i = 0
        fun at(k: Int) = c.getOrNull(k)
        while (i < c.length) {
            val ch = c[i]; val next = at(i + 1); val prev = at(i - 1)
            val first = toks.isEmpty() || prev == '-'
            val last = i == c.length - 1 || next == '-'
            val geresh = next == '\'' 
            val t: Pair<String, Boolean>? = when (ch) {
                'א' -> if (first || last) "a" to true else null
                'ב' -> (if (first) "b" else "v") to false
                'ג' -> (if (geresh) "j" else "g") to false
                'ד' -> "d" to false
                'ה' -> if (last && !first) "a" to true else "h" to false
                'ו' -> when {
                    next == 'ו' -> { i++; "v" to false }
                    first -> "v" to false
                    else -> "o" to true
                }
                'ז' -> (if (geresh) "zh" else "z") to false
                'ח' -> "ch" to false
                'ט' -> "t" to false
                'י' -> when {
                    next == 'י' -> { i++; (if (first) "y" else "ey") to !first }
                    first -> "y" to false
                    else -> "i" to true
                }
                'כ' -> (if (first) "k" else "ch") to false
                'ך' -> "ch" to false
                'ל' -> "l" to false
                'מ', 'ם' -> "m" to false
                'נ', 'ן' -> "n" to false
                'ס' -> "s" to false
                'ע' -> if (first || last) "a" to true else null
                'פ' -> (if (first) "p" else "f") to false
                'ף' -> "f" to false
                'צ', 'ץ' -> (if (geresh) "ch" else "tz") to false
                'ק' -> "k" to false
                'ר' -> "r" to false
                'ש' -> "sh" to false
                'ת' -> (if (geresh) "th" else "t") to false
                '\'', '"' -> null
                '-' -> "-" to true
                else -> if (ch in '\u0591'..'\u05C7') null else ch.toString() to true      // vowel points: drop
            }
            if (t != null) toks.add(t)
            i++
        }
        // Hebrew writes few vowels: an 'e' between the first two consonants of a word, and in the middle of three
        val out = StringBuilder()
        for (k in toks.indices) {
            out.append(toks[k].first)
            val a = toks[k]; val b = toks.getOrNull(k + 1); val c2 = toks.getOrNull(k + 2)
            if (b == null || a.second || b.second || a.first == "-") continue
            val startPair = k == 0 || toks[k - 1].first == "-"
            val triple = c2 != null && !c2.second && (k == 0 || toks[k - 1].second)
            if (startPair || triple) out.append('e')
        }
        return out.toString()
    }
}
