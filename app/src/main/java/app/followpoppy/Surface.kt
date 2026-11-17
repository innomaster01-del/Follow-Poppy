package app.followpoppy

import kotlin.math.abs
import kotlin.math.floor

/**
 * The street's height along the route, not one number for the whole way: a cell every [STEP] metres of the route,
 * each with the AR height measured there (rays from the camera to that spot, onto the floor, the depth image or
 * Google's street model). Between measured cells the height is interpolated; past the last one it carries on the
 * slope it had (gently, never steeper than [MAX_SLOPE]), and where nothing is known it is the near-floor height [base].
 * Small changes are smoothed so the trail never jumps; a measurement far from what a cell already knows has to be seen
 * again before it is believed (a passing car, a bench).
 */
class GroundProfile {
    private class Cell(var h: Double, var n: Int, var t: Long, var doubt: Int = 0)
    private val cells = HashMap<Int, Cell>()

    fun clear() = cells.clear()
    val size get() = cells.size

    /** A measured height [y] at [s] metres along the route, at time [now] (ms). */
    fun observe(s: Double, y: Double, now: Long) {
        val i = Math.round(s / STEP).toInt()
        val c = cells[i]
        if (c == null) { cells[i] = Cell(y, 1, now); return }
        if (abs(y - c.h) > OUTLIER && c.n >= 3) {                       // far from what we know: needs to be seen again
            c.doubt++
            if (c.doubt < 3) return
            c.h = y; c.n = 1; c.doubt = 0; c.t = now; return
        }
        c.doubt = 0
        val k = if (c.n < 4) 0.5 else 0.2                                // settle fast at first, then hold steady
        c.h += (y - c.h) * k; c.n++; c.t = now
    }

    /** True when the cell at [s] has been measured in the last [maxAge] ms. */
    fun known(s: Double, now: Long, maxAge: Long = 15_000): Boolean = cells[Math.round(s / STEP).toInt()]?.let { now - it.t < maxAge } ?: false

    /**
     * The height at [s]: measured cells, smoothed with their neighbours and interpolated; past the measured ones the
     * slope carries on; with nothing measured, [base]. [base] also anchors the first few metres near [you].
     */
    fun heightAt(s: Double, base: Double, you: Double): Double {
        if (cells.isEmpty() || s < you + NEAR) return base
        fun smooth(i: Int): Double? {                                    // a cell averaged with its known neighbours
            val c = cells[i] ?: return null
            var sum = c.h * 2; var w = 2.0
            for (j in listOf(i - 1, i + 1)) cells[j]?.let { sum += it.h; w += 1.0 }
            return sum / w
        }
        val x = s / STEP; val i0 = floor(x).toInt(); val f = x - i0
        val a = smooth(i0); val b = smooth(i0 + 1)
        val h = when {
            a != null && b != null -> a + (b - a) * f
            else -> {
                // the nearest measured cells before and after (within reach)
                val before = cells.keys.filter { it <= i0 }.maxOrNull()
                val after = (i0 + 1..i0 + 1 + REACH).firstOrNull { cells.containsKey(it) }
                when {
                    before != null && after != null && i0 - before <= REACH -> { val hb = smooth(before)!!; val ha = smooth(after)!!; hb + (ha - hb) * (x - before) / (after - before) }
                    before != null -> {                                  // carry the slope on, gently
                        val hb = smooth(before)!!; val prev = (before - 1 downTo before - 3).firstOrNull { cells.containsKey(it) }
                        val slope = if (prev == null) 0.0 else ((hb - smooth(prev)!!) / ((before - prev) * STEP)).coerceIn(-MAX_SLOPE, MAX_SLOPE)
                        hb + slope * minOf((x - before) * STEP, CARRY) * 0.6
                    }
                    after != null -> smooth(after)!!
                    else -> base
                }
            }
        }
        // the first metres after the near field blend from the floor under you into the profile (no step at its start)
        val blend = ((s - you - NEAR) / BLEND).coerceIn(0.0, 1.0)
        return base + (h - base) * blend
    }

    companion object {
        const val STEP = 2.0          // m of route per cell
        const val OUTLIER = 0.45      // m: further than this from a settled cell needs repeating
        const val MAX_SLOPE = 0.15    // a slope carried on past the measured part is never steeper than this
        const val REACH = 6           // cells to look for a measured neighbour
        const val NEAR = 2.0          // m ahead of you where the floor under you (base) rules
        const val BLEND = 4.0         // m over which the profile takes over from it
        const val CARRY = 10.0        // m past the last measured cell the slope carries on (then it stays level)
    }
}

/**
 * Can the trail be shown? From how well ARCore tracks and how recently and how consistently the floor was seen:
 *  GOOD    the floor is seen, steady: the whole trail
 *  PARTIAL seen a little while ago, or only Google's terrain: a shorter trail (the next ~14 m)
 *  LOST    nothing seen for a while, or you are far from the route with no floor (indoors): no trail, no Poppy
 *  BROKEN  ARCore is not tracking: stop and say what to do
 * Changes wait a moment so nothing flickers: a better state after [UP_MS] of it, a worse one after [DOWN_MS]
 * (BROKEN after [BROKEN_MS]). [reach] eases towards the state's length, so the trail grows out and shrinks back.
 */
class SurfaceConfidence {
    enum class State { GOOD, PARTIAL, LOST, BROKEN }
    var state = State.LOST; private set
    /** 0..1: how much of the state's trail is drawn (eases, so it grows out / shrinks back). */
    var shown = 0.0; private set
    private var candidate = State.LOST; private var since = 0L; private var last = 0L

    /**
     * [tracking]: ARCore is tracking; [floorAgo]: ms since a floor hit (Long.MAX_VALUE: never); [hits]: floor hits in the
     * last 3 s; [spread]: their spread in m; [terrain]: Google's terrain under you is fresh; [offset]: m from the route.
     */
    fun update(now: Long, tracking: Boolean, floorAgo: Long, hits: Int, spread: Double, terrain: Boolean, offset: Double): State {
        val want = when {
            !tracking -> State.BROKEN
            offset > FAR_FROM_ROUTE && floorAgo > 1_500 -> State.LOST            // indoors, away from the street
            floorAgo < 1_500 && hits >= 4 && spread < 0.15 -> State.GOOD
            floorAgo < 5_000 || terrain -> State.PARTIAL
            else -> State.LOST
        }
        if (want != candidate) { candidate = want; since = now }
        val wait = when {
            want == State.BROKEN -> BROKEN_MS
            want.ordinal < state.ordinal -> UP_MS                                // better
            else -> DOWN_MS
        }
        if (want != state && now - since >= wait) state = want
        val dt = if (last == 0L) 0.0 else ((now - last) / 1000.0).coerceIn(0.0, 0.2); last = now
        val target = if (state == State.GOOD || state == State.PARTIAL) 1.0 else 0.0
        shown += (target - shown) * (1 - kotlin.math.exp(-dt / 0.35))
        if (abs(target - shown) < 0.01) shown = target
        return state
    }

    /** How far ahead (m) the trail may go now. */
    fun reach(full: Double): Double = when (state) { State.GOOD -> full; State.PARTIAL -> minOf(full, PARTIAL_REACH); else -> full } * shown

    companion object {
        const val UP_MS = 1_000L
        const val DOWN_MS = 2_000L
        const val BROKEN_MS = 500L
        const val PARTIAL_REACH = 14.0
        const val FAR_FROM_ROUTE = 20.0
    }
}
