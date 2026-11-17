package app.followpoppy

import android.graphics.Bitmap
import android.util.Log
import com.google.android.filament.Engine
import com.google.android.filament.MaterialInstance
import io.github.sceneview.geometries.Geometry
import io.github.sceneview.loaders.MaterialLoader
import io.github.sceneview.loaders.ModelLoader
import io.github.sceneview.math.Position
import io.github.sceneview.node.GeometryNode
import io.github.sceneview.texture.ImageTexture
import io.github.sceneview.math.Scale
import io.github.sceneview.node.ModelNode
import io.github.sceneview.node.Node
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.sin

/**
 * The way ahead drawn in 3D on the street (so Poppy stands in front of it and nothing is cut out):
 * a see-through ribbon with white edges, one continuous surface that follows the rounded route (straight edges, no
 * seams, both ends melting away), raised white chevrons that glide forward, Poppy's paw prints from you to her, and her
 * soft shadow. The chevrons, prints and shadow are pooled model nodes under [parent]; unused ones are hidden.
 */
class Trail3D(private val engine: Engine, private val materialLoader: MaterialLoader, private val modelLoader: ModelLoader, private val parent: Node, gender: String) {
    private val pawFile = "models/poppy_paw_$gender.glb"
    private val chevrons = ArrayList<ModelNode>(); private val paws = ArrayList<ModelNode>()
    private var shadow: ModelNode? = null
    private var ribbon: GeometryNode? = null
    private var ribbonFailed = false
    private var rounded: RoundedRoute? = null; private var roundedFor: Route? = null
    private val ribbonIdx = RibbonShape.indices(SECTIONS)

    /** The ribbon's mesh and look, made once: [SECTIONS] cross-sections, the cyan-and-white texture drawn in code. */
    private fun ribbonNode(): GeometryNode? {
        ribbon?.let { return it }
        if (ribbonFailed) return null
        return runCatching {
            val px = RibbonShape.texture(TEX_W, TEX_H)
            val bmp = Bitmap.createBitmap(TEX_W, TEX_H, Bitmap.Config.ARGB_8888).apply { isPremultiplied = false; setPixels(px, 0, TEX_W, 0, 0, TEX_W, TEX_H) }
            val tex = ImageTexture.Builder().bitmap(bmp).build(engine)
            val mat: MaterialInstance = materialLoader.createImageInstance(tex)
            val verts = List(SECTIONS * 2) { i -> Geometry.Vertex(position = Position(0f, -50f, 0f), uvCoordinate = dev.romainguy.kotlin.math.Float2((i % 2).toFloat(), 0.5f)) }
            val geo = Geometry.Builder().vertices(verts).indices(ribbonIdx).build(engine)
            GeometryNode(engine, geo, mat, builderApply = { culling(false); priority(2); castShadows(false); receiveShadows(false) })
                .also { it.isVisible = false; parent.addChildNode(it); ribbon = it }
        }.onFailure { ribbonFailed = true; Log.e("FollowPoppy", "ribbon mesh", it) }.getOrNull()
    }

    private fun take(pool: ArrayList<ModelNode>, i: Int, file: String): ModelNode? {
        while (pool.size <= i) {
            val n = runCatching { ModelNode(modelLoader.createModelInstance(file), autoAnimate = false) }.getOrNull() ?: return null
            n.isVisible = false; parent.addChildNode(n); pool.add(n)
        }
        return pool[i]
    }
    private fun place(n: ModelNode, p: V3, yaw: Double, sx: Double = 1.0, sy: Double = 1.0, sz: Double = 1.0) {
        n.worldPosition = Position(p.x.toFloat(), p.y.toFloat(), p.z.toFloat())
        n.worldQuaternion = dev.romainguy.kotlin.math.Quaternion(0f, sin(yaw / 2).toFloat(), 0f, cos(yaw / 2).toFloat())
        n.scale = Scale(sx.toFloat(), sy.toFloat(), sz.toFloat())
        n.isVisible = true
    }
    private fun hideFrom(pool: ArrayList<ModelNode>, i: Int) { for (k in i until pool.size) pool[k].isVisible = false }

    fun hideAll() { ribbon?.isVisible = false; hideFrom(chevrons, 0); hideFrom(paws, 0); shadow?.isVisible = false }

    /**
     * [route] in map metres, [toAr] maps a map point to the AR ground at height y, [ground] the street's height at a
     * distance along the route, [you] your distance along the route, [reach] how far ahead the trail may go now (the
     * surface confidence: shorter or none when the floor is not seen well), [poppy] her pose (her distance along it is
     * [poppyAlong], NaN when she is off the route), [time] seconds.
     */
    fun update(route: Route, toAr: (Enu, Double) -> V3, ground: (Double) -> Double, you: Double, reach: Double, poppyAlong: Double, poppy: PoppyGuide.Pose, time: Double) {
        val line = route.line
        fun y0(s: Double) = ground(s) + LIFT
        // how far to draw: up to FAR_TO ahead, but only a few metres past the next turn (so the way round the corner is
        // shown without a long bar through the houses beyond it)
        val nextTurn = route.steps.firstOrNull { it.along > you + FADE_TO && (it.modifier.contains("left") || it.modifier.contains("right")) && it.type != "arrive" }
        val end = minOf(you + FAR_TO, route.length, nextTurn?.let { it.along + AFTER_TURN } ?: Double.MAX_VALUE, you + FADE_FROM + reach)
        if (reach < 0.5) { hideAll(); return }
        val start = you + FADE_FROM
        if (roundedFor !== route) { rounded = RoundedRoute(line); roundedFor = route }
        val rr = rounded!!
        val node = ribbonNode()
        if (node != null) {
            if (end - start < 1.0) node.isVisible = false
            else {
                // one surface: cross-sections on a fixed grid along the rounded route, edges straight, no overlaps
                val secs = RibbonShape.sections(rr, start, end, RIBBON_WIDTH, FADE_TO - FADE_FROM, minOf(FAR_TO - FAR_FROM, (end - start) * 0.3), SECTION_STEP, SECTIONS)
                val verts = ArrayList<Geometry.Vertex>(SECTIONS * 2)
                for (sc in secs) for ((k, e) in listOf(0 to sc.left, 1 to sc.right)) {
                    val p = toAr(e, y0(sc.s))
                    verts.add(Geometry.Vertex(position = Position(p.x.toFloat(), p.y.toFloat(), p.z.toFloat()), uvCoordinate = dev.romainguy.kotlin.math.Float2(k.toFloat(), sc.v.toFloat())))
                }
                runCatching { node.updateGeometry(vertices = verts, indices = listOf(ribbonIdx)) }.onFailure { Log.w("FollowPoppy", "ribbon update: ${it.message}") }
                node.isVisible = true
            }
        }
        // chevrons every 3 m, gliding forward
        val flow = (time * 1.1) % CHEVRON_EVERY
        var c = 0
        var s = floor((you + FADE_TO - 0.4 - flow) / CHEVRON_EVERY) * CHEVRON_EVERY + flow
        if (s < you + FADE_TO - 0.4) s += CHEVRON_EVERY
        while (s < minOf(end - 2.0, route.length - 1.0)) {
            if (poppyAlong.isNaN() || kotlin.math.abs(s - poppyAlong) > 0.7) {
                val n = take(chevrons, c, "models/trail_chevron.glb") ?: break
                val p = toAr(line.at(s), y0(s) + 0.01); val q = toAr(line.at(s + 0.5), y0(s + 0.5) + 0.01)
                place(n, p, atan2(q.x - p.x, q.z - p.z)); c++
            }
            s += CHEVRON_EVERY
        }
        hideFrom(chevrons, c)
        // Poppy's paw prints: on a fixed grid along the route (so they stay put on the street), from you to just behind her
        var k = 0
        if (!poppyAlong.isNaN()) {
            var i = kotlin.math.ceil((you + 0.9) / PAW_EVERY).toInt()
            while (i * PAW_EVERY < poppyAlong - 0.45 && k < 40) {
                val d = i * PAW_EVERY; val side = if (i % 2 == 0) 1.0 else -1.0
                val e = line.at(d); val f = line.at(d + 0.3); val dx = f.e - e.e; val dn = f.n - e.n; val l = hypot(dx, dn).coerceAtLeast(1e-6)
                val off = Enu(e.e + (-dn / l) * PAW_SIDE * side, e.n + (dx / l) * PAW_SIDE * side)    // left / right of the line
                val p = toAr(off, y0(d) + 0.006); val q = toAr(Enu(off.e + dx, off.n + dn), y0(d + 0.3) + 0.006)
                val n = take(paws, k, pawFile) ?: break
                place(n, p, atan2(q.x - p.x, q.z - p.z) + side * 0.12, 1.25, 1.0, 1.25); k++; i++
            }
        }
        hideFrom(paws, k)
        // her shadow: on the ground under her, smaller while she is in the air
        val sh = shadow ?: runCatching { ModelNode(modelLoader.createModelInstance("models/poppy_shadow.glb"), autoAnimate = false) }.getOrNull()?.also { parent.addChildNode(it); shadow = it }
        sh?.let { val k2 = (1.0 - poppy.hop * 2.0).coerceIn(0.5, 1.0) * SHADOW_SIZE; place(it, V3(poppy.ground.x, poppy.ground.y + 0.005, poppy.ground.z), poppy.yaw, k2, 1.0, k2 * 0.9) }
    }

    companion object {
        const val SECTIONS = 110       // cross-sections in the ribbon mesh (every SECTION_STEP, both ends exact)
        const val SECTION_STEP = 0.5
        const val TEX_W = 128; const val TEX_H = 512
        const val AFTER_TURN = 5.0     // the trail goes this far past the next turn
        const val RIBBON_WIDTH = 0.85
        const val LIFT = 0.03         // a few cm above the street, so depth occlusion does not nibble it
        const val FAR_FROM = 40.0     // the far end starts fading here (m ahead of you) …
        const val FAR_TO = 48.0       // … and is gone here
        const val FADE_FROM = 0.8     // the ribbon starts fading in here (m ahead of you) …
        const val FADE_TO = 3.2       // … and is full from here
        const val CHEVRON_EVERY = 3.0
        const val PAW_EVERY = 0.34
        const val PAW_SIDE = 0.09
        const val SHADOW_SIZE = 0.62
    }
}
