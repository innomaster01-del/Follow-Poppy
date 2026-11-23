package app.followpoppy

import com.google.ar.core.Coordinates2d
import com.google.ar.core.Frame
import com.google.ar.core.SemanticLabel

/**
 * What each part of the camera picture is (ARCore Scene Semantics: sidewalk, road, grass, building, fence, tree, sky …),
 * so the trail only stands on something you can walk on: a hit on a window sill, a glass pane, a table, a fence or a
 * bush is not the street. Also tells when you are most likely indoors (no sky, trees, cars or road for a while although
 * the phone looked ahead), so the trail is not drawn in the living room.
 *
 * Not every phone has it (ARCore decides); without it everything works as before ([ok] stays false).
 */
class SceneLabels {
    var ok = false; private set
    private var w = 0; private var h = 0
    private var lab = ByteArray(0); private var conf = ByteArray(0)
    private val tmp = FloatArray(2); private val out = FloatArray(2)
    private val outdoor = ArrayDeque<Pair<Long, Float>>()       // (time, outdoor evidence) while looking ahead
    var lastOutdoorAt = 0L; private set

    /** Copies this frame's labels (call every few frames, while tracking). [lookingAhead]: the camera sees the horizon. */
    fun update(frame: Frame, now: Long, lookingAhead: Boolean) {
        val got = runCatching {
            frame.acquireSemanticImage().use { im -> copy(im, false) }
            frame.acquireSemanticConfidenceImage().use { im -> copy(im, true) }
            true
        }.getOrDefault(false)
        if (got) ok = true
        if (!ok) return
        if (lookingAhead) {
            val e = runCatching {
                frame.getSemanticLabelFraction(SemanticLabel.SKY) + frame.getSemanticLabelFraction(SemanticLabel.TREE) +
                    frame.getSemanticLabelFraction(SemanticLabel.ROAD) + frame.getSemanticLabelFraction(SemanticLabel.VEHICLE)
            }.getOrDefault(1f)
            outdoor.addLast(now to e)
            if (e > OUTDOOR_EVIDENCE) lastOutdoorAt = now
        }
        while (outdoor.isNotEmpty() && now - outdoor.first().first > WINDOW_MS) outdoor.removeFirst()
    }

    /**
     * Most likely indoors: for [WINDOW_MS] the phone looked ahead often enough and never saw sky, trees, cars or road.
     * (Looking down at the sidewalk only says nothing either way.)
     */
    fun indoors(now: Long): Boolean = ok && outdoor.size >= MIN_LOOKS && now - lastOutdoorAt > WINDOW_MS &&
        outdoor.first().first < now - WINDOW_MS * 0.6

    private fun copy(im: android.media.Image, confidence: Boolean) {
        val p = im.planes[0]; val iw = im.width; val ih = im.height
        val buf = p.buffer; val rs = p.rowStride; val ps = p.pixelStride
        val dst = if (confidence) conf else lab
        val arr = if (dst.size == iw * ih) dst else ByteArray(iw * ih)
        if (ps == 1 && rs == iw) { buf.rewind(); buf.get(arr, 0, iw * ih) }
        else for (y in 0 until ih) for (x in 0 until iw) arr[y * iw + x] = buf.get(y * rs + x * ps)
        if (confidence) conf = arr else lab = arr
        w = iw; h = ih
    }

    /** The label (C API numbers, see [WALKABLE]) and its confidence 0..255 at a point of the view (pixels), or null. */
    fun at(frame: Frame, x: Float, y: Float): Pair<Int, Int>? {
        if (!ok || w == 0 || lab.size != w * h) return null
        tmp[0] = x; tmp[1] = y
        runCatching { frame.transformCoordinates2d(Coordinates2d.VIEW, tmp, Coordinates2d.IMAGE_NORMALIZED, out) }.getOrElse { return null }
        val px = (out[0] * w).toInt(); val py = (out[1] * h).toInt()
        if (px !in 0 until w || py !in 0 until h) return null
        val i = py * w + px
        return (lab[i].toInt() and 0xff) to (if (conf.size == lab.size) conf[i].toInt() and 0xff else 255)
    }

    /** Can this point of the view be walked on? true = sidewalk / road / grass, false = surely not, null = can't tell. */
    fun walkable(frame: Frame, x: Float, y: Float): Boolean? = judge(at(frame, x, y))

    companion object {
        // ArSemanticLabel values
        const val UNLABELED = 0; const val SKY = 1; const val BUILDING = 2; const val TREE = 3; const val ROAD = 4; const val SIDEWALK = 5
        const val TERRAIN = 6; const val STRUCTURE = 7; const val OBJECT = 8; const val VEHICLE = 9; const val PERSON = 10; const val WATER = 11
        val WALKABLE = setOf(ROAD, SIDEWALK, TERRAIN)
        const val SURE = 110                 // of 255: below this a "not walkable" label is not trusted
        const val OUTDOOR_EVIDENCE = 0.02f   // share of the picture that is sky / trees / road / cars
        const val WINDOW_MS = 12_000L
        const val MIN_LOOKS = 20

        fun judge(l: Pair<Int, Int>?): Boolean? = when {
            l == null -> null
            l.first in WALKABLE -> true
            l.first == UNLABELED || l.second < SURE -> null
            else -> false
        }
    }
}
