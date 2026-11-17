package app.followpoppy

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.offset
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import java.net.URL
import kotlin.math.PI
import kotlin.math.atan
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.hypot
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sinh
import kotlin.math.tan

/**
 * Where a map point lands on a Mapbox static image: Web Mercator (512 px tiles) around [center] at [zoom], the map turned
 * so that [bearing] (degrees, clockwise from north) points up. Returns logical pixels from the image's top-left.
 * (Used by the small corner map's image.)
 */
internal object StaticMapProjection {
    private fun size(zoom: Double) = 512.0 * Math.pow(2.0, zoom)
    private fun world(p: LatLng, zoom: Double): DoubleArray {
        val s = size(zoom); val lat = Math.toRadians(p.lat.coerceIn(-85.0, 85.0))
        return doubleArrayOf((p.lng + 180) / 360 * s, (1 - ln(tan(lat) + 1 / cos(lat)) / PI) / 2 * s)
    }
    fun project(p: LatLng, center: LatLng, zoom: Double, bearing: Double, w: Double, h: Double): DoubleArray {
        val a = world(p, zoom); val c = world(center, zoom)
        val dx = a[0] - c[0]; val dy = a[1] - c[1]; val b = Math.toRadians(bearing)
        return doubleArrayOf(w / 2 + dx * cos(b) + dy * sin(b), h / 2 - dx * sin(b) + dy * cos(b))
    }
}

/**
 * Web Mercator for map tiles: a 256-unit tile grid (one unit = one logical pixel at that zoom). The view turns so that
 * its bearing points up; a world point at zoom [z] maps to the screen around the view centre.
 */
internal object TileMath {
    const val TILE = 256.0
    fun world(p: LatLng, z: Int): DoubleArray {
        val s = TILE * (1 shl z); val lat = Math.toRadians(p.lat.coerceIn(-85.0, 85.0))
        return doubleArrayOf((p.lng + 180) / 360 * s, (1 - ln(tan(lat) + 1 / cos(lat)) / PI) / 2 * s)
    }
    fun fromWorld(x: Double, y: Double, z: Int): LatLng {
        val s = TILE * (1 shl z)
        return LatLng(Math.toDegrees(atan(sinh(PI * (1 - 2 * y / s)))), x / s * 360 - 180)
    }
    /** Logical pixels per metre at [lat] and fractional zoom [zoom]. */
    fun pxPerMetre(lat: Double, zoom: Double) = TILE * Math.pow(2.0, zoom) / (40_075_016.7 * cos(Math.toRadians(lat)))
}

/** Map tiles in memory: the most recently used ones (a tile is 512 x 512, 16-bit colour, half a megabyte). */
private class TileCache(private val max: Int = 70) {
    private val map = object : LinkedHashMap<Long, ImageBitmap>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<Long, ImageBitmap>?) = size > max
    }
    val loading = HashSet<Long>()
    val failed = HashMap<Long, Long>()
    @Synchronized operator fun get(k: Long) = map[k]
    @Synchronized fun put(k: Long, b: ImageBitmap) { map[k] = b }
    companion object { fun key(z: Int, x: Int, y: Int) = (z.toLong() shl 48) or (x.toLong() shl 24) or y.toLong() }
}

/**
 * The route on a live street map: map tiles (so zooming and dragging are smooth, with no waiting for a new picture),
 * turned the way you face while it follows you. Pinch to zoom, drag to look around; a button brings it back to you.
 * The route as a dotted line, Poppy, you (an arrow), the destination flag and a scale bar.
 */
@Composable
internal fun RouteMap(w: Words, api: MapboxApi, route: Route?, along: Double, poppyAlong: Double, at: () -> LatLng?, heading: () -> Double,
                      gender: String, modifier: Modifier = Modifier, startZoom: Double = 16.6, bottomInset: Float = 0f, topInset: Float = 0f, centerY: Float = 0.55f, inDisc: Boolean = false) {
    val dens = LocalDensity.current.density
    val scope = rememberCoroutineScope()
    val cache = remember { TileCache() }
    val gate = remember { Semaphore(6) }
    var tilesVersion by remember { mutableIntStateOf(0) }
    var zoom by remember { mutableDoubleStateOf(startZoom) }
    var free by remember { mutableStateOf<LatLng?>(null) }              // null = following you; else the centre you dragged to
    var freeBearing by remember { mutableDoubleStateOf(0.0) }
    var bearing by remember { mutableDoubleStateOf(Double.NaN) }       // smoothed heading while following
    var frame by remember { mutableLongStateOf(0L) }
    val tint = if (gender == "boy") Color(0xFF5FB3FF) else Color(0xFFFF7FBF)
    val routeBlue = Color(0xFF1A73E8)
    // the map turns smoothly with you (a little each frame), and you and Poppy move on it
    LaunchedEffect(Unit) {
        while (true) {
            delay(33); frame++
            val h = heading()
            if (!h.isNaN()) bearing = if (bearing.isNaN()) h else (bearing + Math.toDegrees(GeoAlign.wrap(Math.toRadians(h - bearing))) * 0.12 + 360) % 360
        }
    }
    fun need(z: Int, x: Int, y: Int) {
        val n = 1 shl z; if (y < 0 || y >= n) return
        val xx = ((x % n) + n) % n; val k = TileCache.key(z, xx, y)
        if (cache[k] != null || k in cache.loading) return
        val f = cache.failed[k]; if (f != null && System.currentTimeMillis() - f < 15_000) return
        cache.loading.add(k)
        scope.launch {
            val bm = gate.withPermit {
                runCatching { withContext(Dispatchers.IO) {
                    URL(api.tileUrl(z, xx, y)).openStream().use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.RGB_565 }) }
                } }.onFailure { Log.w("FollowPoppy", "tile $z/$xx/$y: ${it.message}") }.getOrNull()
            }
            cache.loading.remove(k)
            if (bm != null) { cache.put(k, bm.asImageBitmap()); tilesVersion++ } else cache.failed[k] = System.currentTimeMillis()
        }
    }
    Box(modifier) {
        Canvas(Modifier.fillMaxSize().pointerInput(Unit) {
            detectTransformGestures { _, pan, gz, _ ->
                val b = if (free != null) freeBearing else bearing.let { if (it.isNaN()) 0.0 else it }
                val c0 = free ?: at() ?: return@detectTransformGestures
                zoom = (zoom + ln(gz.toDouble()) / ln(2.0)).coerceIn(12.0, 19.5)
                if (pan.getDistance() > 0.5f || free != null) {
                    // the drag in screen pixels → map units at this zoom, turned back by the bearing
                    val z = zoom.roundToInt(); val s = Math.pow(2.0, zoom - z) * dens
                    val br = Math.toRadians(b); val px = -pan.x / s; val py = -pan.y / s
                    val dx = px * cos(br) - py * sin(br); val dy = px * sin(br) + py * cos(br)
                    val c = TileMath.world(c0, z)
                    if (free == null) freeBearing = b
                    free = TileMath.fromWorld(c[0] + dx, c[1] + dy, z)
                }
            }
        }) {
            frame.let { }; tilesVersion.let { }                                // redraw on time and on new tiles
            val vc = free ?: at() ?: return@Canvas
            val b = if (free != null) freeBearing else bearing.let { if (it.isNaN()) 0.0 else it }
            val z = zoom.roundToInt().coerceIn(1, 20)
            val s = Math.pow(2.0, zoom - z)                                    // logical units per tile unit
            val k = (s * dens).toFloat()
            val cx = size.width / 2; val cy = topInset + (size.height - bottomInset - topInset) * centerY
            val c = TileMath.world(vc, z)
            // tiles covering the turned view (a circle around the centre is enough)
            val r = hypot(max(cx, size.width - cx).toDouble(), max(cy, size.height - cy).toDouble()) / k
            val t0x = floor((c[0] - r) / TileMath.TILE).toInt(); val t1x = floor((c[0] + r) / TileMath.TILE).toInt()
            val t0y = floor((c[1] - r) / TileMath.TILE).toInt(); val t1y = floor((c[1] + r) / TileMath.TILE).toInt()
            drawRect(Color(0xFFEDEFF2))
            withTransform({ translate(cx, cy); rotate(-b.toFloat(), Offset.Zero); scale(k, k, Offset.Zero) }) {
                for (ty in t0y..t1y) for (tx in t0x..t1x) {
                    need(z, tx, ty)
                    val n = 1 shl z; val xx = ((tx % n) + n) % n
                    val ox = (tx * TileMath.TILE - c[0]).toFloat(); val oy = (ty * TileMath.TILE - c[1]).toFloat()
                    val img = cache[TileCache.key(z, xx, ty)]
                    if (img != null) translate(ox, oy) { drawImage(img, dstSize = IntSize(257, 257)) }
                    else {
                        // not here yet: the parent tile, enlarged, until it comes
                        val p = cache[TileCache.key(z - 1, xx / 2, ty / 2)]
                        if (p != null) translate(ox, oy) {
                            drawImage(p, srcOffset = androidx.compose.ui.unit.IntOffset((xx % 2) * p.width / 2, (ty % 2) * p.height / 2),
                                srcSize = IntSize(p.width / 2, p.height / 2), dstSize = IntSize(257, 257))
                        }
                    }
                }
            }
            fun px(p: LatLng): Offset {
                val q = TileMath.world(p, z); val dx = (q[0] - c[0]) * k; val dy = (q[1] - c[1]) * k; val br = Math.toRadians(b)
                return Offset((cx + dx * cos(br) + dy * sin(br)).toFloat(), (cy - dx * sin(br) + dy * cos(br)).toFloat())
            }
            val metrePx = (TileMath.pxPerMetre(vc.lat, zoom) * dens).toFloat()
            val rt = route
            if (rt != null) {
                fun g(sAlong: Double) = Geo.fromEnu(rt.line.origin, rt.line.at(sAlong))
                // the route as dots, like a maps app: the walked part faded; a dot every ~9 px
                val done = along.coerceIn(0.0, rt.length)
                val step = (9 * dens / metrePx).toDouble().coerceAtLeast(0.5)
                val dot = (3.6f * dens).coerceAtMost(metrePx * 1.6f).coerceAtLeast(2.2f * dens)
                var sA = 0.0
                while (sA <= rt.length) {
                    val p = px(g(sA))
                    if (p.x > -20 && p.y > -20 && p.x < size.width + 20 && p.y < size.height + 20) {
                        if (sA < done) drawCircle(routeBlue.copy(alpha = 0.3f), dot * 0.8f, p)
                        else { drawCircle(Color.White, dot + 1.2f * dens, p); drawCircle(routeBlue, dot, p) }
                    }
                    sA += step
                }
                // destination: a ring (as in a maps app) and a little flag
                val d = px(g(rt.length))
                drawCircle(Color.White, 9f * dens, d); drawCircle(Color(0xFF202124), 9f * dens, d, style = Stroke(3f * dens))
                drawLine(Color(0xFF202124), d + Offset(0f, -9f * dens), d + Offset(0f, -26f * dens), 2.5f * dens)
                drawPath(Path().apply { moveTo(d.x, d.y - 26f * dens); lineTo(d.x + 14f * dens, d.y - 21f * dens); lineTo(d.x, d.y - 16f * dens); close() }, Color(0xFFF5B841))
                if (!poppyAlong.isNaN()) miniPoppy(px(g(poppyAlong)), tint, dens / 2.6f)
            }
            // you: a blue arrow with a white rim; up while following (the map turns), turned when you moved the map
            at()?.let { p ->
                val me = px(p); val u = dens
                val rot = if (free == null) 0f else (heading().let { if (it.isNaN()) b else it } - b).toFloat()
                drawCircle(Color(0x331A73E8), 26f * u, me)
                rotate(rot, me) {
                    drawPath(Path().apply { moveTo(me.x, me.y - 15f * u); lineTo(me.x + 11f * u, me.y + 11f * u); lineTo(me.x, me.y + 5f * u); lineTo(me.x - 11f * u, me.y + 11f * u); close() }, Color.White)
                    drawPath(Path().apply { moveTo(me.x, me.y - 11f * u); lineTo(me.x + 8f * u, me.y + 8.5f * u); lineTo(me.x, me.y + 4f * u); lineTo(me.x - 8f * u, me.y + 8.5f * u); close() }, routeBlue)
                }
            }
            if (!inDisc) scaleBar(metrePx, dens, bottomInset)
        }
        // back to following you
        if (free != null) Box((if (inDisc) Modifier.align(Alignment.BottomCenter).padding(bottom = 70.dp) else Modifier.align(Alignment.TopEnd).padding(top = (topInset / dens).dp + 12.dp, end = 16.dp)).size(44.dp).clip(CircleShape)
            .background(Color.White).border(1.dp, Color(0x22000000), CircleShape).clickable { free = null; zoom = startZoom }, contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(20.dp)) {
                val s = size.width
                drawPath(Path().apply { moveTo(s * 0.9f, s * 0.1f); lineTo(s * 0.55f, s * 0.92f); lineTo(s * 0.45f, s * 0.55f); lineTo(s * 0.08f, s * 0.45f); close() }, routeBlue)
            }
        }
    }
}

/** A short scale bar (bottom-left): a round number of metres and its length. */
private fun DrawScope.scaleBar(metrePx: Float, dens: Float, bottomInset: Float) {
    if (metrePx <= 0f) return
    val want = 90 * dens / metrePx
    val nice = listOf(10, 20, 50, 100, 200, 500, 1000, 2000, 5000).lastOrNull { it <= want } ?: 10
    val len = nice * metrePx; val x = 16 * dens; val y = size.height - bottomInset - 14 * dens
    drawLine(Color(0x66000000), Offset(x, y), Offset(x + len, y), 6f, StrokeCap.Round)
    drawLine(Color(0xFF3C4043), Offset(x, y), Offset(x + len, y), 3f, StrokeCap.Round)
    drawContext.canvas.nativeCanvas.drawText(if (nice >= 1000) "${nice / 1000} km" else "$nice m", x, y - 7 * dens, android.graphics.Paint().apply {
        color = android.graphics.Color.rgb(60, 64, 67); textSize = 12 * dens; isAntiAlias = true; isFakeBoldText = true
    })
}

/**
 * The map that comes up with a tap, like a phone's live-view maps: a round map lying on the ground in front of you
 * (a disc seen in perspective), its rim fading softly into the camera picture, the street map filling it. It turns
 * with you; pinch and drag it. The pill at the top closes it (tap, or drag it down).
 */
@Composable
internal fun MapSheet(w: Words, api: MapboxApi, route: Route?, along: Double, poppyAlong: Double, at: () -> LatLng?, heading: () -> Double,
                      gender: String, remaining: String, bottomInset: Float, onClose: () -> Unit) {
    var drag by remember { mutableFloatStateOf(0f) }
    val dens = LocalDensity.current.density
    androidx.compose.foundation.layout.BoxWithConstraints(Modifier.fillMaxWidth().height(470.dp).graphicsLayer { translationY = drag }) {
        val d = maxWidth * 1.12f
        Box(
            Modifier.align(Alignment.TopCenter).offset(y = 20.dp).requiredSize(d)
                .graphicsLayer {
                    rotationX = 50f; cameraDistance = 9f * density; transformOrigin = TransformOrigin(0.5f, 0.5f)   // lying on the ground
                    compositingStrategy = CompositingStrategy.Offscreen
                }
                .drawWithContent {
                    drawContent()
                    // the rim fades into the camera picture
                    drawRect(Brush.radialGradient(0f to Color.Black, 0.80f to Color.Black, 1f to Color.Transparent, center = center, radius = size.minDimension / 2), blendMode = BlendMode.DstIn)
                }
                .clip(CircleShape)
        ) {
            RouteMap(w, api, route, along, poppyAlong, at, heading, gender, Modifier.fillMaxSize(), startZoom = 17.2, centerY = 0.5f, inDisc = true)
        }
        // close: a small pill at the top (tap, or drag it down)
        Row(Modifier.align(Alignment.TopCenter).padding(top = 6.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xFF1A73E8))
            .pointerInput(Unit) { detectVerticalDragGestures(onDragEnd = { if (drag > 120f) onClose(); drag = 0f }, onDragCancel = { drag = 0f }) { _, dy -> drag = (drag + dy).coerceAtLeast(0f) } }
            .clickable { onClose() }.padding(horizontal = 16.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
            Canvas(Modifier.size(14.dp)) {                                     // a check mark
                drawPath(Path().apply { moveTo(size.width * 0.1f, size.height * 0.55f); lineTo(size.width * 0.4f, size.height * 0.85f); lineTo(size.width * 0.92f, size.height * 0.2f) }, Color.White, style = Stroke(2.4f * dens, cap = StrokeCap.Round))
            }
            Spacer(Modifier.width(6.dp))
            Text(w.t("סגירה", "Done") + " · " + remaining, color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        }
    }
}

/** A tiny Poppy for the map: a fluffy ball with two long ears and two eyes, outlined in white. */
private fun DrawScope.miniPoppy(c: Offset, tint: Color, k: Float) {
    val r = 15f * k
    for (sx in listOf(-1f, 1f)) {
        drawOval(Color.White, Offset(c.x + sx * r * 0.42f - r * 0.32f, c.y - r * 2.05f), Size(r * 0.64f, r * 1.5f))
        drawOval(tint, Offset(c.x + sx * r * 0.42f - r * 0.24f, c.y - r * 1.97f), Size(r * 0.48f, r * 1.34f))
    }
    drawCircle(Color.White, r + 3f * k, c); drawCircle(tint, r, c)
    for (sx in listOf(-1f, 1f)) { drawCircle(Color(0xFF1C1622), r * 0.2f, Offset(c.x + sx * r * 0.36f, c.y - r * 0.05f)); drawCircle(Color.White, r * 0.07f, Offset(c.x + sx * r * 0.36f + 1.5f * k, c.y - r * 0.12f)) }
    drawCircle(Color(0x66FF7BA8), r * 0.14f, Offset(c.x - r * 0.62f, c.y + r * 0.25f)); drawCircle(Color(0x66FF7BA8), r * 0.14f, Offset(c.x + r * 0.62f, c.y + r * 0.25f))
    drawArc(Color(0xFF2A1A24), 20f, 140f, false, Offset(c.x - r * 0.22f, c.y + r * 0.1f), Size(r * 0.44f, r * 0.3f), style = Stroke(width = 2.5f * k))
}
