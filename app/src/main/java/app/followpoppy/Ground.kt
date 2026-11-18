package app.followpoppy

import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.hypot

/**
 * The street's height in AR from many hit tests (floor planes and ARCore depth) across the lower part of the camera view.
 * Bushes, benches and kerbs also answer, so the floor is taken low in the spread of recent answers (20th percentile)
 * rather than their average. Null when nothing answered recently.
 */
class GroundFinder(private val windowMs: Long = 2500) {
    private val ys = ArrayDeque<Pair<Long, Double>>()
    var lastHitAt = 0L; private set
    fun add(t: Long, y: Double) { ys.addLast(t to y); lastHitAt = t; while (ys.size > 80) ys.removeFirst() }
    /** How many answers came in the last [windowMs] (drives the scan progress). */
    fun count(now: Long): Int = ys.count { now - it.first < windowMs }
    /** A strong answer: a tap on the floor counts as several. */
    fun addStrong(t: Long, y: Double) { repeat(6) { add(t, y) } }
    /** How far apart the recent answers are (m, 20th to 80th percentile): small = one steady floor. */
    fun spread(now: Long): Double {
        val r = ys.filter { now - it.first < windowMs }.map { it.second }.sorted()
        return if (r.size < 3) Double.MAX_VALUE else r[(r.size * 0.8).toInt().coerceAtMost(r.size - 1)] - r[(r.size * 0.2).toInt()]
    }
    fun estimate(now: Long): Double? {
        val recent = ys.filter { now - it.first < windowMs }.map { it.second }.sorted()
        return if (recent.size < 3) null else recent[(recent.size * 0.2).toInt()]
    }
}

/**
 * Keeps the drawn route on the sidewalk you actually walk on. The map's walking line and your GPS position disagree by
 * a few metres sideways (and the map line often runs down the middle of the street); while you are near the route, the
 * whole drawing is shifted by your sideways distance from the line, so the trail starts at your feet.
 */
class SidewalkSnap {
    var e = 0.0; private set
    var n = 0.0; private set
    fun update(user: Enu, line: Polyline, along: Double, offset: Double, gain: Double = 0.15) {
        if (offset > MAX) { e *= 0.97; n *= 0.97; return }
        val p = line.at(along); val a = line.at((along - 3).coerceAtLeast(0.0)); val b = line.at((along + 3).coerceAtMost(line.length))
        val te = b.e - a.e; val tn = b.n - a.n; val tl = hypot(te, tn); if (tl < 1e-6) return
        val ue = te / tl; val un = tn / tl
        val de = user.e - p.e; val dn = user.n - p.n
        val side = de * (-un) + dn * ue                                         // signed sideways distance (left of the line +)
        val we = -un * side; val wn = ue * side
        e += (we - e) * gain; n += (wn - n) * gain
    }
    fun apply(p: Enu) = Enu(p.e + e, p.n + n)
    fun reset() { e = 0.0; n = 0.0 }
    companion object { const val MAX = 18.0 }
}

/**
 * Corrects the compass with your own walking: while you are near the route and walk a straight stretch, the direction you
 * moved in AR is the route's direction on the map there. It does not need your progress along the route to be right
 * (a wrong compass is exactly what stops that from advancing), only that you stay near a straight part of the route and
 * your walking is within [MAX_OFF] degrees of it. Returns (AR dx, AR dz, map bearing in degrees) for GeoAlign, or null.
 */
class MotionHeading {
    private var start: V3? = null; private var last: V3? = null; private var path = 0.0
    fun update(cam: V3, along: Double, offset: Double, line: Polyline, mapAngleOfAr: (Double, Double) -> Double): DoubleArray? {
        val s0 = start; val l = last
        if (s0 == null || l == null || offset > 12) { start = cam; last = cam; path = 0.0; return null }
        path += hypot(cam.x - l.x, cam.z - l.z); last = cam
        val dx = cam.x - s0.x; val dz = cam.z - s0.z; val moved = hypot(dx, dz)
        if (moved < 6) { if (path > 12) { start = cam; path = 0.0 }; return null }
        val straight = path <= moved * 1.15
        start = cam; path = 0.0
        if (!straight) return null                                              // you did not walk straight
        // the route around where you are must be straight
        val b0 = bearing(line, along - 8, along); val b1 = bearing(line, along, along + 8)
        if (abs(GeoAlign.wrap(Math.toRadians(b1 - b0))) > Math.toRadians(12.0)) return null
        val route = bearing(line, along - 8, along + 8)
        // where the current alignment says you walked, on the map; a big difference is a street crossing, not compass error
        val walkedMap = mapAngleOfAr(dx, dz)
        if (abs(GeoAlign.wrap(Math.toRadians(walkedMap - route))) > Math.toRadians(MAX_OFF)) return null
        return doubleArrayOf(dx, dz, route)
    }
    private fun bearing(line: Polyline, s0: Double, s1: Double): Double {
        val a = line.at(s0.coerceIn(0.0, line.length)); val b = line.at(s1.coerceIn(0.0, line.length))
        return (Math.toDegrees(atan2(b.e - a.e, b.n - a.n)) + 360) % 360
    }
    companion object { const val MAX_OFF = 50.0 }
}

/**
 * GPS without pulling you back: a fix describes where the phone was when it was measured (often most of a second
 * before it arrives), so it is compared with the AR position at that moment, not the current one. ARCore's own tracking
 * is far better over short distances, so after the start a fix only corrects slow drift (time constant grows with the
 * fix's error), and a fix far from where AR says you are is ignored unless several in a row agree.
 */
class GpsBlend {
    private val hist = ArrayDeque<Pair<Long, V3>>()
    private var lastFixNs = 0L
    private var outliers = 0
    /** Record where the camera is now ([ns] = SystemClock.elapsedRealtimeNanos()). */
    fun record(ns: Long, cam: V3) { hist.addLast(ns to cam); while (hist.size > 120) hist.removeFirst() }
    /** The camera position when the fix was measured, or null when that is older than the history. */
    fun camAt(ns: Long): V3? {
        if (hist.isEmpty() || ns < hist.first().first) return null
        var best = hist.last()
        for (h in hist) if (abs(h.first - ns) < abs(best.first - ns)) best = h
        return best.second
    }
    /**
     * Gain for a fix measured at [ns] with accuracy [acc] m whose position disagrees with AR by [innovation] m.
     * 0 = ignore it.
     */
    fun gain(ns: Long, acc: Double, innovation: Double, settled: Boolean): Double {
        val dt = if (lastFixNs == 0L) 1.0 else ((ns - lastFixNs) / 1e9).coerceIn(0.1, 5.0); lastFixNs = ns
        val a = acc.coerceAtLeast(3.0)
        if (innovation > maxOf(3 * a, 25.0)) { outliers++; if (outliers < 4) return 0.0 } else outliers = 0
        if (!settled) return (9.0 / (a * a)).coerceIn(0.02, 0.5)
        if (a > 20) return 0.0
        val tau = 8.0 + 2.0 * a                                               // ±5 m: 18 s, ±15 m: 38 s
        return 1 - kotlin.math.exp(-dt / tau)
    }
}
