package app.followpoppy

import kotlin.math.abs
import kotlin.math.acos
import kotlin.math.hypot
import kotlin.math.tan

/**
 * The route with its corners rounded, in map metres, computed once per route (so the trail's shape never wobbles as you
 * walk). Each point keeps its distance along the original route, so "from 1 m ahead of you to 40 m" still means the same
 * stretch of street.
 */
class RoundedRoute(line: Polyline, radius: Double = RADIUS) {
    val along: DoubleArray
    val pts: List<Enu>

    init {
        val p = line.pts; val c = line.cum
        val outA = ArrayList<Double>(); val outP = ArrayList<Enu>()
        outA.add(0.0); outP.add(p.first())
        for (i in 1 until p.size - 1) {
            val a = p[i - 1]; val b = p[i]; val d = p[i + 1]
            val l1 = c[i] - c[i - 1]; val l2 = c[i + 1] - c[i]
            if (l1 < 1e-6 || l2 < 1e-6) continue
            val u1e = (b.e - a.e) / l1; val u1n = (b.n - a.n) / l1; val u2e = (d.e - b.e) / l2; val u2n = (d.n - b.n) / l2
            val turn = acos((u1e * u2e + u1n * u2n).coerceIn(-1.0, 1.0))           // 0 = straight on
            if (turn < 0.03) { outA.add(c[i]); outP.add(b); continue }
            val t = minOf(radius * tan(turn / 2), l1 * 0.45, l2 * 0.45)              // where the curve leaves / joins the legs
            val t1 = Enu(b.e - u1e * t, b.n - u1n * t); val t2 = Enu(b.e + u2e * t, b.n + u2n * t)
            for (k in 0..CURVE_STEPS) {                                               // a smooth curve through the corner
                val u = k.toDouble() / CURVE_STEPS; val w0 = (1 - u) * (1 - u); val w1 = 2 * u * (1 - u); val w2 = u * u
                outP.add(Enu(w0 * t1.e + w1 * b.e + w2 * t2.e, w0 * t1.n + w1 * b.n + w2 * t2.n)); outA.add(c[i] - t + 2 * t * u)
            }
        }
        outA.add(c.last()); outP.add(p.last())
        along = outA.toDoubleArray(); pts = outP
    }

    /** The point of the rounded route at distance [s] along the original route. */
    fun at(s: Double): Enu {
        val x = s.coerceIn(along.first(), along.last())
        var i = 0; while (i < along.size - 2 && along[i + 1] < x) i++
        val seg = along[i + 1] - along[i]; val t = if (seg < 1e-9) 0.0 else (x - along[i]) / seg
        return Enu(pts[i].e + (pts[i + 1].e - pts[i].e) * t, pts[i].n + (pts[i + 1].n - pts[i].n) * t)
    }

    /** Unit direction of travel at [s] (east, north). */
    fun dir(s: Double): Enu {
        val a = at(s - 0.25); val b = at(s + 0.25); val l = hypot(b.e - a.e, b.n - a.n)
        return if (l < 1e-9) Enu(0.0, 1.0) else Enu((b.e - a.e) / l, (b.n - a.n) / l)
    }

    companion object { const val RADIUS = 2.5; const val CURVE_STEPS = 8 }
}

/**
 * The cross-sections of the trail between [start] and [end] (distances along the route): one every [step] metres on a
 * fixed grid (so they stay put on the street as you walk), plus both ends exactly. Each has its left and right edge in map
 * metres and the texture row v: 0 at the near end, 0.5 in the full part, 1 at the far end (the ends melt away there).
 * Always [count] sections (the last repeats), so the mesh keeps the same size every frame.
 */
object RibbonShape {
    data class Section(val left: Enu, val right: Enu, val v: Double)

    fun sections(r: RoundedRoute, start: Double, end: Double, width: Double, nearFade: Double, farFade: Double, step: Double, count: Int): List<Section> {
        val ss = ArrayList<Double>()
        ss.add(start)
        var g = (kotlin.math.floor(start / step) + 1) * step
        while (g < end - 1e-6 && ss.size < count - 1) { if (g - ss.last() > step * 0.25) ss.add(g); g += step }
        ss.add(end)
        val len = (end - start).coerceAtLeast(1e-6)
        val nf = minOf(nearFade, len * 0.4); val ff = minOf(farFade, len * 0.4)
        val out = ss.map { s ->
            val p = r.at(s); val d = r.dir(s); val h = width / 2
            val left = Enu(p.e - d.n * h, p.n + d.e * h); val right = Enu(p.e + d.n * h, p.n - d.e * h)
            val a = s - start; val b = end - s
            val v = when { a < nf -> 0.5 * a / nf; b < ff -> 1 - 0.5 * b / ff; else -> 0.5 }
            Section(left, right, v)
        }.toMutableList()
        while (out.size < count) out.add(out.last())
        return out
    }

    /** Triangle indices for [count] sections (two triangles between neighbours; left = 2i, right = 2i + 1). */
    fun indices(count: Int): List<Int> = buildList { for (i in 0 until count - 1) { val a = 2 * i; addAll(listOf(a, a + 2, a + 1, a + 1, a + 2, a + 3)) } }

    /**
     * The ribbon's look as RGBA pixels (straight alpha), [w] across (u: left → right) and [h] along (v): see-through cyan
     * with soft white edges in the middle rows; towards both ends (v → 0 and v → 1) a smooth fade with fine sparkles.
     * The same seen from either end, so it does not matter which way up the texture is uploaded.
     */
    fun texture(w: Int = 128, h: Int = 512): IntArray {
        fun ss(x: Double): Double { val t = x.coerceIn(0.0, 1.0); return t * t * (3 - 2 * t) }
        val alpha = DoubleArray(w * h); val white = DoubleArray(w * h)
        for (y in 0 until h) for (x in 0 until w) {
            val v = (y + 0.5) / h; val t = 1 - abs(v - 0.5) / 0.5                        // 0 at either end, 1 in the middle
            val u = (x + 0.5) / w
            val ramp = ss((t - 0.05) / 0.85)
            val edge = (maxOf(0.0, 1 - abs(u - 0.035) / 0.03) + maxOf(0.0, 1 - abs(u - 0.965) / 0.03)).coerceAtMost(1.0)
            alpha[y * w + x] = BODY * ramp * (1 - edge) + EDGE * edge * ss((t - 0.15) / 0.75)
            white[y * w + x] = edge
        }
        var seed = 4242L
        fun rnd(): Double { seed = (seed * 1103515245 + 12345) and 0x7fffffff; return seed.toDouble() / 0x7fffffff }
        repeat(2 * SPARKLES) { i ->                                                       // sparkles near both ends
            val t = 0.06 + rnd() * 0.72; val cx = 6 + rnd() * (w - 12); val r = 0.8 + rnd() * 1.3
            val cy = (if (i % 2 == 0) t * 0.5 else 1 - t * 0.5) * (h - 1)
            val a = 0.6 * ss((t - 0.06) / 0.22) * (1 - (t - 0.06) / 0.72) * (0.45 + 0.55 * rnd())
            for (y in (cy - r - 1).toInt()..(cy + r + 1).toInt()) for (x in (cx - r - 1).toInt()..(cx + r + 1).toInt()) {
                if (x < 0 || y < 0 || x >= w || y >= h) continue
                val k = (r - hypot(x + 0.5 - cx, y + 0.5 - cy) + 0.5).coerceIn(0.0, 1.0)      // anti-aliased disc
                val idx = y * w + x
                if (a > alpha[idx]) alpha[idx] += (a - alpha[idx]) * k
                white[idx] = maxOf(white[idx], 0.6 * k)
            }
        }
        return IntArray(w * h) { i ->
            val wt = white[i]; val a = (alpha[i].coerceIn(0.0, 1.0) * 255).toInt()
            val rr = (34 + (255 - 34) * wt).toInt(); val gg = (211 + (255 - 211) * wt).toInt(); val bb = (238 + (255 - 238) * wt).toInt()
            (a shl 24) or (rr shl 16) or (gg shl 8) or bb
        }
    }

    const val BODY = 0.24
    const val EDGE = 0.72
    const val SPARKLES = 95
}
