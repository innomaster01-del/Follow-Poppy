package app.followpoppy

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sinh
import kotlin.math.tan

/**
 * Where people actually walk along the route. Walking routes are drawn on the middle of the street (the map has the
 * street, not always its sidewalks), so the trail would lie on the road. This moves it onto the sidewalk:
 *  1. the sidewalks themselves, where the map has them (Mapbox Streets: path type "sidewalk", from OpenStreetMap);
 *  2. else beside the road by its kind (a small street is narrower than a main road), never into a building;
 *  3. where the route already is a footpath, a pedestrian street or a park path, it stays on it.
 * One side of the street for the whole route (the side you walk on; it flips when you keep walking on the other one),
 * so at corners the trail goes round the corner, over the crossing, like a person does.
 */

// ---------------------------------------------------------------- vector tiles (Mapbox Streets v8, protobuf)

/** A minimal reader for Mapbox Vector Tiles: features of some layers, their properties and geometry (0..1 of the tile). */
object Mvt {
    class Feature(val layer: String, val props: Map<String, Any>, val type: Int, val parts: List<List<DoubleArray>>)

    private class Pb(val b: ByteArray, var p: Int = 0, val end: Int = b.size) {
        fun more() = p < end
        fun varint(): Long { var r = 0L; var s = 0; while (true) { val x = b[p++].toInt() and 0xff; r = r or ((x and 0x7f).toLong() shl s); if (x < 0x80) return r; s += 7 } }
        fun bytes(): Pb { val n = varint().toInt(); val q = Pb(b, p, p + n); p += n; return q }
        fun skip(wire: Int) { when (wire) { 0 -> varint(); 1 -> p += 8; 2 -> { val n = varint().toInt(); p += n }; 5 -> p += 4; else -> p = end } }
        fun string() = bytes().let { String(b, it.p, it.end - it.p, Charsets.UTF_8) }
        fun packed(): IntArray { val q = bytes(); val out = ArrayList<Int>(); while (q.more()) out.add(q.varint().toInt()); return out.toIntArray() }
    }

    fun decode(data: ByteArray, layers: Set<String>): List<Feature> {
        val bytes = if (data.size > 2 && data[0] == 0x1f.toByte() && data[1] == 0x8b.toByte())
            java.util.zip.GZIPInputStream(data.inputStream()).readBytes() else data
        val out = ArrayList<Feature>()
        val t = Pb(bytes)
        while (t.more()) {
            val key = t.varint().toInt()
            if (key shr 3 == 3 && key and 7 == 2) layer(t.bytes(), layers, out) else t.skip(key and 7)
        }
        return out
    }

    private fun layer(l: Pb, want: Set<String>, out: MutableList<Feature>) {
        var name = ""; var extent = 4096
        val keys = ArrayList<String>(); val values = ArrayList<Any>(); val feats = ArrayList<Pb>()
        while (l.more()) {
            val key = l.varint().toInt()
            when (key shr 3) {
                1 -> name = l.string()
                2 -> feats.add(l.bytes())
                3 -> keys.add(l.string())
                4 -> values.add(value(l.bytes()))
                5 -> extent = l.varint().toInt()
                else -> l.skip(key and 7)
            }
        }
        if (name !in want) return
        for (f in feats) {
            var tags = IntArray(0); var type = 0; var geom = IntArray(0)
            while (f.more()) {
                val key = f.varint().toInt()
                when (key shr 3) { 2 -> tags = f.packed(); 3 -> type = f.varint().toInt(); 4 -> geom = f.packed(); else -> f.skip(key and 7) }
            }
            val props = HashMap<String, Any>()
            var i = 0
            while (i + 1 < tags.size) { keys.getOrNull(tags[i])?.let { k -> values.getOrNull(tags[i + 1])?.let { props[k] = it } }; i += 2 }
            out.add(Feature(name, props, type, geometry(geom, extent.toDouble())))
        }
    }

    private fun value(v: Pb): Any {
        var r: Any = ""
        while (v.more()) {
            val key = v.varint().toInt()
            r = when (key shr 3) {
                1 -> v.string()
                2 -> { val x = java.nio.ByteBuffer.wrap(v.b, v.p, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).float; v.p += 4; x.toDouble() }
                3 -> { val x = java.nio.ByteBuffer.wrap(v.b, v.p, 8).order(java.nio.ByteOrder.LITTLE_ENDIAN).double; v.p += 8; x }
                4, 5 -> v.varint()
                6 -> v.varint().let { (it ushr 1) xor -(it and 1) }
                7 -> v.varint() != 0L
                else -> { v.skip(key and 7); r }
            }
        }
        return r
    }

    private fun geometry(g: IntArray, extent: Double): List<List<DoubleArray>> {
        val parts = ArrayList<MutableList<DoubleArray>>()
        var x = 0; var y = 0; var i = 0
        fun zz(n: Int) = (n ushr 1) xor -(n and 1)
        while (i < g.size) {
            val cmd = g[i] and 7; val count = g[i] ushr 3; i++
            when (cmd) {
                1, 2 -> repeat(count) {
                    if (i + 1 >= g.size) return parts
                    x += zz(g[i]); y += zz(g[i + 1]); i += 2
                    if (cmd == 1) parts.add(ArrayList())
                    parts.lastOrNull()?.add(doubleArrayOf(x / extent, y / extent))
                }
                7 -> parts.lastOrNull()?.let { p -> if (p.isNotEmpty()) p.add(p.first()) }
                else -> return parts
            }
        }
        return parts
    }

    /** The tile (x, y) at zoom [z] holding a place. */
    fun tileOf(at: LatLng, z: Int): IntArray {
        val n = 1 shl z
        val x = floor((at.lng + 180) / 360 * n).toInt()
        val r = Math.toRadians(at.lat)
        val y = floor((1 - ln(tan(r) + 1 / cos(r)) / PI) / 2 * n).toInt()
        return intArrayOf(x, y)
    }

    /** A point of tile (x, y, z) given 0..1 inside it, as a place. */
    fun place(z: Int, x: Int, y: Int, fx: Double, fy: Double): LatLng {
        val n = (1 shl z).toDouble()
        val lng = (x + fx) / n * 360 - 180
        val lat = Math.toDegrees(atan(sinh(PI * (1 - 2 * (y + fy) / n))))
        return LatLng(lat, lng)
    }
}

// ---------------------------------------------------------------- what the map knows around the route

class StreetData(val walks: List<Way>, val sidewalks: List<Way>, val roads: List<Way>, val buildings: List<List<Enu>>, val names: Map<String, String> = emptyMap()) {
    /** A line of the map: its kind (road class, or path type) and its points in the route's metres. */
    class Way(val kind: String, val pts: List<Enu>)

    companion object {
        const val ZOOM = 16
        /** Half the width of a road (middle to kerb), by its kind. */
        val HALF = mapOf("motorway" to 12.0, "trunk" to 10.0, "primary" to 9.0, "secondary" to 7.5, "tertiary" to 6.0,
            "street" to 4.5, "street_limited" to 3.5, "service" to 3.0, "motorway_link" to 6.0, "trunk_link" to 5.0,
            "primary_link" to 5.0, "secondary_link" to 4.5, "tertiary_link" to 4.0, "track" to 2.0)
        private val WALK_TYPES = setOf("sidewalk", "crossing", "footway", "path", "steps", "corridor", "trail", "hiking")

        /**
         * The map around [line] (every tile the route passes, and its neighbours within ~40 m), from [tile] (z, x, y) →
         * the tile's bytes, or null. At most [maxTiles] tiles. Call off the main thread.
         */
        fun load(line: Polyline, tile: (Int, Int, Int) -> ByteArray?, maxTiles: Int = 40): StreetData {
            val want = LinkedHashSet<Long>()
            var s = 0.0
            while (s <= line.length && want.size < maxTiles) {
                val p = line.at(s)
                for ((de, dn) in listOf(0.0 to 0.0, 40.0 to 0.0, -40.0 to 0.0, 0.0 to 40.0, 0.0 to -40.0)) {
                    val t = Mvt.tileOf(Geo.fromEnu(line.origin, Enu(p.e + de, p.n + dn)), ZOOM)
                    want.add(t[0].toLong() shl 32 or t[1].toLong())
                }
                s += 20.0
            }
            val walks = ArrayList<Way>(); val sidewalks = ArrayList<Way>(); val roads = ArrayList<Way>(); val buildings = ArrayList<List<Enu>>()
            val names = HashMap<String, String>()          // a street's local (Hebrew) name → its English name, for English mode
            for (k in want.take(maxTiles)) {
                val x = (k shr 32).toInt(); val y = (k and 0xffffffffL).toInt()
                val bytes = runCatching { tile(ZOOM, x, y) }.getOrNull() ?: continue
                val feats = runCatching { Mvt.decode(bytes, setOf("road", "building")) }.getOrElse { emptyList() }
                for (f in feats) {
                    val parts = f.parts.map { part -> part.map { q -> Geo.toEnu(line.origin, Mvt.place(ZOOM, x, y, q[0], q[1])) } }.filter { it.size >= 2 }
                    if (f.layer == "building") { if (f.type == 3) buildings.addAll(parts); continue }
                    if (f.type != 2) continue
                    val local = f.props["name"] as? String; val en = f.props["name_en"] as? String
                    if (local != null && en != null && HebrewLatin.has(local) && !HebrewLatin.has(en)) names[local] = en
                    val cls = f.props["class"] as? String ?: continue
                    val type = f.props["type"] as? String ?: ""
                    when {
                        cls == "path" && type in WALK_TYPES -> { parts.forEach { walks.add(Way(type, it)) }; if (type == "sidewalk" || type == "footway") parts.forEach { sidewalks.add(Way(type, it)) } }
                        cls == "pedestrian" -> parts.forEach { walks.add(Way(cls, it)) }
                        cls in HALF -> parts.forEach { roads.add(Way(cls, it)) }
                    }
                }
            }
            return StreetData(walks, sidewalks, roads, buildings, names)
        }
    }
}

// ---------------------------------------------------------------- the plan: how far left / right of the middle

/**
 * For every [STEP] metres of the route's line: whether it already is a walkway, and on each side how far from the
 * middle the sidewalk is (NaN: no idea) and how that was found (2 = the map's sidewalk, 1 = beside the road, 0 = none).
 */
class SidewalkPlan(val onWalk: BooleanArray, val left: DoubleArray, val right: DoubleArray, val leftHow: IntArray, val rightHow: IntArray) {
    val size get() = onWalk.size

    /** Distances (m, + left of the direction of walking) for the whole route on [side] (+1 left, -1 right), smoothed. */
    fun lateral(side: Int): DoubleArray {
        val raw = DoubleArray(size) { i ->
            if (onWalk[i]) 0.0 else {
                val v = if (side > 0) left[i] else right[i]
                if (v.isNaN()) 0.0 else v * side
            }
        }
        // a short median (one odd sample does not bend the trail), then no faster sideways than SLEW per step
        val med = DoubleArray(size) { i -> (max(0, i - 2)..min(size - 1, i + 2)).map { raw[it] }.sorted().let { it[it.size / 2] } }
        for (i in 1 until size) med[i] = med[i].coerceIn(med[i - 1] - SLEW, med[i - 1] + SLEW)
        for (i in size - 2 downTo 0) med[i] = med[i].coerceIn(med[i + 1] - SLEW, med[i + 1] + SLEW)
        return med
    }

    /** How much of the route (0..1, not counting walkways) has the map's own sidewalk on [side]. */
    fun mapped(side: Int): Double {
        val road = (0 until size).filter { !onWalk[it] }
        if (road.isEmpty()) return 1.0
        return road.count { (if (side > 0) leftHow[it] else rightHow[it]) == 2 }.toDouble() / road.size
    }
    fun walkShare() = if (size == 0) 0.0 else onWalk.count { it }.toDouble() / size

    companion object {
        const val STEP = 2.0
        const val SLEW = 1.2               // m sideways per STEP at most (about 30°): the trail eases onto / off the sidewalk
        const val SIDEWALK_MIN = 1.5       // a sidewalk this close to the middle is the route's own line
        const val SIDEWALK_MAX = 16.0
        const val KERB_TO_MIDDLE = 1.5     // from the kerb to the middle of the sidewalk
        const val FROM_WALL = 1.0          // never closer to a building than this

        fun build(line: Polyline, d: StreetData): SidewalkPlan {
            val n = (line.length / STEP).toInt() + 1
            val onWalk = BooleanArray(n); val left = DoubleArray(n) { Double.NaN }; val right = DoubleArray(n) { Double.NaN }
            val lh = IntArray(n); val rh = IntArray(n)
            val walkGrid = Grid(d.walks.map { it.pts }); val swGrid = Grid(d.sidewalks.map { it.pts }); val roadGrid = Grid(d.roads.map { it.pts }); val kindOf = java.util.IdentityHashMap<List<Enu>, String>().also { m -> d.roads.forEach { m[it.pts] = it.kind } }; val bGrid = Grid(d.buildings)
            for (i in 0 until n) {
                val s = min(i * STEP, line.length)
                val p = line.at(s); val a = line.at(s - 1.5); val b = line.at(s + 1.5)
                var te = b.e - a.e; var tn = b.n - a.n; val tl = hypot(te, tn); if (tl < 1e-6) continue
                te /= tl; tn /= tl
                val ne = -tn; val nn = te                                                    // left of the direction
                // the route is a walkway here: a path along it, right under it
                onWalk[i] = walkGrid.near(p, 3.0).any { (w, j) -> val q = w[j]; val r = w[j + 1]; segDist(p, q, r) < 2.0 && parallel(q, r, te, tn, 0.8) }
                if (onWalk[i]) { left[i] = 0.0; right[i] = 0.0; continue }
                // the road under the route: how wide it is
                var half = Double.NaN; var best = 3.0
                for ((w, j) in roadGrid.near(p, 3.0)) {
                    val q = w[j]; val r = w[j + 1]; val dd = segDist(p, q, r)
                    if (dd < best && parallel(q, r, te, tn, 0.8)) { best = dd; half = StreetData.HALF[kindOf[w] ?: "street"] ?: 4.5 }
                }
                // buildings either side (a ray across the street)
                val bl = ray(bGrid, p, ne, nn, 1.0, 40.0); val br = ray(bGrid, p, -ne, -nn, 1.0, 40.0)
                // the map's sidewalks either side: lines along the street, crossed by the ray
                val sl = ray(swGrid, p, ne, nn, SIDEWALK_MIN, SIDEWALK_MAX, te, tn); val sr = ray(swGrid, p, -ne, -nn, SIDEWALK_MIN, SIDEWALK_MAX, te, tn)
                fun pick(sw: Double, wall: Double): Pair<Double, Int> = when {
                    !sw.isNaN() && (wall.isNaN() || sw < wall) -> sw to 2
                    !half.isNaN() -> {
                        var v = half + KERB_TO_MIDDLE
                        if (!wall.isNaN()) v = min(v, max(wall - FROM_WALL, half + 0.4))
                        v to 1
                    }
                    else -> Double.NaN to 0
                }
                pick(sl, bl).let { left[i] = it.first; lh[i] = it.second }
                pick(sr, br).let { right[i] = it.first; rh[i] = it.second }
            }
            return SidewalkPlan(onWalk, left, right, lh, rh)
        }

        private fun parallel(q: Enu, r: Enu, te: Double, tn: Double, minCos: Double): Boolean {
            val de = r.e - q.e; val dn = r.n - q.n; val l = hypot(de, dn); if (l < 1e-6) return false
            return abs((de * te + dn * tn) / l) >= minCos
        }

        internal fun segDist(p: Enu, a: Enu, b: Enu): Double {
            val dx = b.e - a.e; val dy = b.n - a.n; val l2 = dx * dx + dy * dy
            val t = if (l2 < 1e-12) 0.0 else (((p.e - a.e) * dx + (p.n - a.n) * dy) / l2).coerceIn(0.0, 1.0)
            return hypot(p.e - (a.e + dx * t), p.n - (a.n + dy * t))
        }

        /**
         * The nearest crossing of the ray p + (de, dn)·u, u in [lo, hi], with the lines of [g] (if [te], [tn] are given, only
         * lines running along that direction). NaN when none.
         */
        private fun ray(g: Grid, p: Enu, de: Double, dn: Double, lo: Double, hi: Double, te: Double = Double.NaN, tn: Double = Double.NaN): Double {
            var best = Double.NaN
            val mid = Enu(p.e + de * hi / 2, p.n + dn * hi / 2)
            for ((w, j) in g.near(mid, hi / 2 + 2)) {
                val a = w[j]; val b = w[j + 1]
                if (!te.isNaN() && !parallel(a, b, te, tn, 0.85)) continue
                val ex = b.e - a.e; val ey = b.n - a.n
                val den = de * ey - dn * ex; if (abs(den) < 1e-9) continue
                val ax = a.e - p.e; val ay = a.n - p.n
                val u = (ax * ey - ay * ex) / den; val v = (ax * dn - ay * de) / den
                if (v < 0 || v > 1 || u < lo || u > hi) continue
                if (best.isNaN() || u < best) best = u
            }
            return best
        }
    }

    /** Line segments bucketed in 10 m cells, for quick "what is near here" (each answer: the line and its segment). */
    private class Grid(private val lines: List<List<Enu>>) {
        private val cells = HashMap<Long, MutableList<Long>>()
        private fun key(x: Int, y: Int) = (x.toLong() shl 32) or (y.toLong() and 0xffffffffL)
        init {
            for ((li, w) in lines.withIndex()) for (j in 0 until w.size - 1) {
                val a = w[j]; val b = w[j + 1]
                val x0 = floor(min(a.e, b.e) / C).toInt(); val x1 = floor(max(a.e, b.e) / C).toInt()
                val y0 = floor(min(a.n, b.n) / C).toInt(); val y1 = floor(max(a.n, b.n) / C).toInt()
                if ((x1 - x0 + 1) * (y1 - y0 + 1) > 400) continue
                for (x in x0..x1) for (y in y0..y1) cells.getOrPut(key(x, y)) { ArrayList() }.add((li.toLong() shl 32) or j.toLong())
            }
        }
        fun near(p: Enu, r: Double): List<Pair<List<Enu>, Int>> {
            val ids = HashSet<Long>()
            for (x in floor((p.e - r) / C).toInt()..floor((p.e + r) / C).toInt()) for (y in floor((p.n - r) / C).toInt()..floor((p.n + r) / C).toInt()) cells[key(x, y)]?.let { ids.addAll(it) }
            return ids.map { lines[(it shr 32).toInt()] to (it and 0xffffffffL).toInt() }
        }
        companion object { const val C = 10.0 }
    }
}

// ---------------------------------------------------------------- the line to draw

/**
 * The route moved sideways by [lat] (m, + left; one value every [SidewalkPlan.STEP] m of the middle line): a line
 * with proper corners (at an outside corner it goes round over the crossing, at an inside corner it cuts in where
 * the two sidewalks meet), and the map between distances along the middle ([toWalk]) and along this line ([toMiddle]).
 */
class WalkLine(val middle: Polyline, lat: DoubleArray) {
    val line: Polyline
    private val sMid: DoubleArray
    private val sWalk: DoubleArray

    init {
        // the middle line with a point every STEP (and at every corner), each with its sideways distance
        val pts = ArrayList<Enu>(); val ss = ArrayList<Double>()
        for (i in 0 until middle.pts.size) {
            val c0 = middle.cum[i]
            if (pts.isNotEmpty() && hypot(middle.pts[i].e - pts.last().e, middle.pts[i].n - pts.last().n) < 0.05) continue   // a repeated point
            pts.add(middle.pts[i]); ss.add(c0)
            if (i + 1 < middle.pts.size) {
                var s = (floor((c0 + 0.3) / SidewalkPlan.STEP) + 1) * SidewalkPlan.STEP
                while (s < middle.cum[i + 1] - 0.3) { pts.add(middle.at(s)); ss.add(s); s += SidewalkPlan.STEP }
            }
        }
        fun latAt(s: Double): Double {
            if (lat.isEmpty()) return 0.0
            val x = s / SidewalkPlan.STEP; val i = floor(x).toInt().coerceIn(0, lat.size - 1); val j = min(i + 1, lat.size - 1)
            return lat[i] + (lat[j] - lat[i]) * (x - i).coerceIn(0.0, 1.0)
        }
        val n = pts.size
        val out = ArrayList<Enu>(); val outS = ArrayList<Double>()
        fun dir(k: Int): DoubleArray { val a = pts[k]; val b = pts[k + 1]; val l = hypot(b.e - a.e, b.n - a.n).coerceAtLeast(1e-9); return doubleArrayOf((b.e - a.e) / l, (b.n - a.n) / l) }
        fun add(p: Enu, s: Double) {
            // drop points behind the new one (an inside corner: the offset legs overlap there)
            while (out.size >= 2) {
                val a = out[out.size - 2]; val b = out[out.size - 1]
                val back = (p.e - b.e) * (b.e - a.e) + (p.n - b.n) * (b.n - a.n) < -0.5 * hypot(p.e - b.e, p.n - b.n) * hypot(b.e - a.e, b.n - a.n)   // turning back (>120°)
                if (back && hypot(p.e - b.e, p.n - b.n) < 3 * abs(latAt(s)) + 2) { out.removeAt(out.size - 1); outS.removeAt(outS.size - 1) } else break
            }
            if (out.isNotEmpty() && hypot(p.e - out.last().e, p.n - out.last().n) < 0.05) return
            out.add(p); outS.add(s)
        }
        for (k in 0 until n) {
            val l = latAt(ss[k])
            if (n < 2) { add(pts[k], ss[k]); continue }
            val dIn = if (k > 0) dir(k - 1) else dir(0)
            val dOut = if (k < n - 1) dir(k) else dir(n - 2)
            val cross = dIn[0] * dOut[1] - dIn[1] * dOut[0]; val dot = dIn[0] * dOut[0] + dIn[1] * dOut[1]
            if (k == 0 || k == n - 1 || abs(cross) < 0.09 && dot > 0) {
                // straight on: sideways along the average direction
                val ae = dIn[0] + dOut[0]; val an = dIn[1] + dOut[1]; val al = hypot(ae, an).coerceAtLeast(1e-9)
                add(Enu(pts[k].e - an / al * l, pts[k].n + ae / al * l), ss[k])
            } else {
                // a corner: where the two moved legs meet (mitre), unless that is far off (a very sharp turn: two points)
                val nIn = doubleArrayOf(-dIn[1], dIn[0]); val nOut = doubleArrayOf(-dOut[1], dOut[0])
                val p1 = Enu(pts[k].e + nIn[0] * l, pts[k].n + nIn[1] * l); val p2 = Enu(pts[k].e + nOut[0] * l, pts[k].n + nOut[1] * l)
                val den = dIn[0] * dOut[1] - dIn[1] * dOut[0]
                val u = ((p2.e - p1.e) * dOut[1] - (p2.n - p1.n) * dOut[0]) / den
                val m = Enu(p1.e + dIn[0] * u, p1.n + dIn[1] * u)
                if (hypot(m.e - pts[k].e, m.n - pts[k].n) <= 3 * abs(l) + 0.5) add(m, ss[k]) else { add(p1, ss[k]); add(p2, ss[k]) }
            }
        }
        if (out.size < 2) { out.clear(); outS.clear(); out.addAll(middle.pts); outS.addAll(middle.cum.toList()) }
        line = Polyline(middle.origin, out.map { Geo.fromEnu(middle.origin, it) })
        sMid = outS.toDoubleArray(); sWalk = line.cum.copyOf()
        for (i in 1 until sMid.size) if (sMid[i] < sMid[i - 1]) sMid[i] = sMid[i - 1]
    }

    /** Distance along the middle line → along this line. */
    fun toWalk(s: Double) = interp(sMid, sWalk, s)
    /** Distance along this line → along the middle line. */
    fun toMiddle(w: Double) = interp(sWalk, sMid, w)

    private fun interp(xs: DoubleArray, ys: DoubleArray, x: Double): Double {
        if (xs.isEmpty()) return x
        if (x <= xs[0]) return ys[0] + (x - xs[0])
        if (x >= xs.last()) return ys.last() + (x - xs.last())
        var lo = 0; var hi = xs.size - 1
        while (hi - lo > 1) { val m = (lo + hi) / 2; if (xs[m] <= x) lo = m else hi = m }
        val span = xs[hi] - xs[lo]
        return if (span < 1e-9) ys[hi] else ys[lo] + (ys[hi] - ys[lo]) * (x - xs[lo]) / span
    }

    /** The route to draw: this line, with the manoeuvres at their places on it. */
    fun route(r: Route) = Route(line, r.steps.map { it.copy(along = toWalk(it.along)) }, r.duration)

    companion object {
        /** Sideways distance (m, + left) of [p] from the middle line at [s]. */
        fun sideOf(middle: Polyline, s: Double, p: Enu): Double {
            val a = middle.at(s - 1.5); val b = middle.at(s + 1.5); val c = middle.at(s)
            val te = b.e - a.e; val tn = b.n - a.n; val tl = hypot(te, tn); if (tl < 1e-6) return 0.0
            return ((p.e - c.e) * (-tn) + (p.n - c.n) * te) / tl
        }
    }
}
