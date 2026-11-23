package app.followpoppy


import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

class WalkGeoTest {
    @Test fun polylineMatchesGoogleExample() {
        val pts = listOf(LatLng(38.5, -120.2), LatLng(40.7, -120.95), LatLng(43.252, -126.453))
        assertEquals("_p~iF~ps|U_ulLnnqC_mqNvxq`@", Geo.encodePolyline(pts))
        val back = Geo.decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        back.zip(pts).forEach { (a, b) -> assertEquals(b.lat, a.lat, 1e-5); assertEquals(b.lng, a.lng, 1e-5) }
    }
    @Test fun distancesAndBearings() {
        val a = LatLng(32.0753, 34.7746); val b = LatLng(32.0808, 34.7813)
        assertEquals(878.0, Geo.distance(a, b), 15.0)
        assertEquals(45.0, Geo.bearing(LatLng(0.0, 0.0), LatLng(0.001, 0.001)), 0.5)
        val e = Geo.toEnu(a, b); val c = Geo.fromEnu(a, e)
        assertEquals(b.lat, c.lat, 1e-9); assertEquals(b.lng, c.lng, 1e-9)
        assertEquals(Geo.distance(a, b), Math.hypot(e.e, e.n), 2.0)
    }
    /** An L-shaped street: 100 m north, then 100 m east, coming back 2 m beside the first leg. */
    private fun lRoute(): Route {
        val o = LatLng(32.0, 34.8)
        val geo = listOf(Enu(0.0, 0.0), Enu(0.0, 100.0), Enu(100.0, 100.0), Enu(100.0, 2.0), Enu(4.0, 2.0)).map { Geo.fromEnu(o, it) }
        val line = Polyline(geo.first(), geo)
        val steps = listOf(
            Step("Head north", "depart", "straight", 0.0, 100.0, "A", geo[0]), Step("Turn right", "turn", "right", 100.0, 100.0, "B", geo[1]),
            Step("Turn right", "turn", "right", 200.0, 98.0, "C", geo[2]), Step("Turn right", "turn", "right", 298.0, 96.0, "D", geo[3]),
            Step("You have arrived", "arrive", "straight", 394.0, 0.0, "", geo[4]))
        return Route(line, steps, 394 / 1.4)
    }
    @Test fun snapNeverJumpsBackToAnEarlierLeg() {
        val r = lRoute(); val o = r.line.origin
        val late = r.line.snap(Enu(50.0, 2.5), from = 330.0)        // walking the last leg, 2 m beside the first one
        assertTrue("snapped to ${late.along}", late.along > 300)
        val early = r.line.snap(Enu(1.0, 50.0), from = 0.0)
        assertEquals(50.0, early.along, 0.5)
        assertEquals(394.0, r.length, 0.01)
        assertEquals(0.0, Geo.distance(o, Geo.fromEnu(o, r.line.at(0.0))), 0.01)
        assertEquals(90.0, r.line.headingAt(150.0), 1.0)
    }
    @Test fun navigatorCuesInOrderAndArrives() {
        val r = lRoute(); val n = Navigator(r); val cues = ArrayList<String>()
        var s = 0.0; var t = 0.0
        while (s <= r.length) { val p = Geo.fromEnu(r.line.origin, r.line.at(s)); n.update(p, 5.0, t).forEach { (c, st) -> cues.add("$c ${st?.along?.toInt()}") }; s += 1.4; t += 1 }
        assertEquals(listOf("PREPARE 100", "NOW 100", "PREPARE 200", "NOW 200", "PREPARE 298", "NOW 298", "ARRIVED 394"), cues)
        assertTrue(n.state.arrived)
    }
    @Test fun navigatorDetectsLeavingTheRoute() {
        val r = lRoute(); val n = Navigator(r)
        val off = Geo.fromEnu(r.line.origin, Enu(-60.0, 40.0))
        n.update(Geo.fromEnu(r.line.origin, r.line.at(5.0)), 5.0, 0.0)                     // on the route first
        val got = (1..13).flatMap { n.update(off, 5.0, it.toDouble()) }.map { it.first }
        assertTrue(Navigator.Cue.OFF_ROUTE in got)
    }
    @Test fun startingAwayFromTheRouteIsNotOffRoute() {
        val r = lRoute(); val n = Navigator(r)
        val home = Geo.fromEnu(r.line.origin, Enu(-60.0, 40.0))                           // at home, the route is over there
        val got = (0..20).flatMap { n.update(home, 5.0, it.toDouble()) }.map { it.first }
        assertFalse(Navigator.Cue.OFF_ROUTE in got); assertFalse(n.joined)
        n.update(Geo.fromEnu(r.line.origin, r.line.at(3.0)), 5.0, 21.0); assertTrue(n.joined)
    }
    @Test fun parsesMapboxDirections() {
        val geo = Geo.encodePolyline(listOf(LatLng(32.0, 34.8), LatLng(32.0009, 34.8), LatLng(32.0009, 34.801)))
        val j = JSONObject("""{"code":"Ok","routes":[{"geometry":"$geo","duration":160,"legs":[{"steps":[
            {"distance":100,"name":"A","maneuver":{"type":"depart","instruction":"Walk north","location":[34.8,32.0]}},
            {"distance":94,"name":"B","maneuver":{"type":"turn","modifier":"right","instruction":"פנה ימינה","location":[34.8,32.0009]}},
            {"distance":0,"name":"","maneuver":{"type":"arrive","instruction":"Arrived","location":[34.801,32.0009]}}]}]}]}""")
        val r = MapboxApi.parseDirections(j)
        assertEquals(3, r.steps.size); assertEquals("פנה ימינה", r.steps[1].instruction); assertEquals("right", r.steps[1].modifier)
        assertEquals(100.0, r.steps[1].along, 1.0); assertEquals(r.length, r.steps[2].along, 1.0)
    }
}

class WalkArTest {
    @Test fun alignmentMapsNorthToWhereTheCompassSays() {
        val g = GeoAlign()
        // the camera looks along AR +x, and the compass says that is east (90°)
        g.heading(1.0, 0.0, 90.0, 1.0); g.position(V3(5.0, 1.5, -3.0), Enu(10.0, 20.0), 1.0)
        val me = g.toAr(Enu(10.0, 20.0), 0.0); assertEquals(5.0, me.x, 1e-9); assertEquals(-3.0, me.z, 1e-9)
        val east = g.toAr(Enu(11.0, 20.0), 0.0); assertEquals(6.0, east.x, 1e-9); assertEquals(-3.0, east.z, 1e-9)   // 1 m east = 1 m along +x
        val north = g.toAr(Enu(10.0, 21.0), 0.0); assertEquals(5.0, north.x, 1e-9); assertEquals(-4.0, north.z, 1e-9) // north is to the left of east: −z
        val back = g.toEnu(V3(6.0, 0.0, -4.0)); assertEquals(11.0, back.e, 1e-9); assertEquals(21.0, back.n, 1e-9)
    }
    @Test fun headingSmoothingWrapsAround() {
        val g = GeoAlign(); g.heading(0.0, -1.0, 359.0, 1.0); g.heading(0.0, -1.0, 1.0, 0.5)
        assertEquals(0.0, Math.toDegrees(-g.yaw), 0.6)
    }
    private fun lookAt(eye: V3, yawDeg: Double): FloatArray {     // camera at eye looking at horizontal angle yaw (0 = −z)
        val a = yawDeg * PI / 180; val fx = sin(a); val fz = -cos(a)
        val r = doubleArrayOf(-fz, 0.0, fx)                       // right = forward × up
        val v = FloatArray(16)
        v[0] = r[0].toFloat(); v[4] = r[1].toFloat(); v[8] = r[2].toFloat(); v[12] = (-(r[0] * eye.x + r[2] * eye.z)).toFloat()
        v[1] = 0f; v[5] = 1f; v[9] = 0f; v[13] = (-eye.y).toFloat()
        v[2] = (-fx).toFloat(); v[6] = 0f; v[10] = (-fz).toFloat(); v[14] = (fx * eye.x + fz * eye.z).toFloat()
        v[15] = 1f; return v
    }
    private fun persp(): FloatArray { val f = 1 / Math.tan(Math.toRadians(30.0)); val n = 0.1; val fa = 200.0
        return FloatArray(16).also { p -> p[0] = (f / 0.5).toFloat(); p[5] = f.toFloat(); p[10] = ((fa + n) / (n - fa)).toFloat(); p[11] = -1f; p[14] = (2 * fa * n / (n - fa)).toFloat() } }
    @Test fun projectsAheadAndClipsBehind() {
        val pj = Projector(lookAt(V3(0.0, 1.5, 0.0), 0.0), persp(), 1000f, 2000f)
        val c = pj.screen(V3(0.0, 1.5, -10.0))!!; assertEquals(500f, c[0], 1f); assertEquals(1000f, c[1], 1f)
        assertNull(pj.screen(V3(0.0, 0.0, 5.0)))                                                 // behind
        val below = pj.screen(V3(0.0, 0.0, -5.0))!!; assertTrue(below[1] > 1000f)               // the ground ahead is below the centre
        val quad = pj.polygon(listOf(V3(-0.5, 0.0, 3.0), V3(-0.5, 0.0, -6.0), V3(0.5, 0.0, -6.0), V3(0.5, 0.0, 3.0)))!!
        assertTrue(quad.size >= 4); quad.forEach { assertTrue(it[1] >= 1000f) }
    }
    @Test fun ribbonFollowsTheRoute() {
        val path = (0..20).map { (it * 2.0) to V3(0.0, 0.0, -it * 2.0) }
        val (q, ch) = Ribbon.build(path, 1.0, 3.0)
        assertEquals(20, q.size); assertEquals(14, ch.size)
        q.forEach { quad -> assertEquals(1.0, abs(quad.pts[0].x - quad.pts[3].x), 1e-9) }
        ch.forEach { c -> assertTrue(c.pts[0].z < c.pts[1].z) }                          // the tip points along the route (−z)
    }
}

class PoppyGuideTest {
    private val ground = { s: Double -> V3(0.0, 0.0, -s) }                                // a straight street along −z
    private fun cam(s: Double) = V3(0.0, 1.45, -s)
    private fun feet(s: Double) = V3(0.0, 0.0, -s)
    private val dt = 1.0 / 30

    @Test fun walksAheadThenWaitsFacingYou() {
        val g = PoppyGuide(); var me = 0.0
        var pose = g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground)
        repeat(30 * 20) { me += 1.4 * dt; pose = g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground) }
        assertEquals(me + PoppyGuide.LEAD, g.along, 0.6)                                // a few metres in front of you
        assertTrue(g.walking); assertEquals(0, pose.clip)
        assertEquals(PI, abs(GeoAlign.wrap(pose.yaw)), 0.15)                          // facing down the street (−z)
        repeat(30 * 5) { pose = g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground) }    // you stop
        assertFalse(g.walking); assertEquals(1, pose.clip)                             // idle clip, not walking on the spot
        assertEquals(me + PoppyGuide.LEAD, g.along, 0.8)                                // she slows down and stops (a little past 4 m is fine)
        assertEquals(0.0, GeoAlign.wrap(pose.yaw), 0.15)                              // she turned round to you
    }

    @Test fun waitingTurnsIntoSittingYawningSleepingAndWakesUp() {
        val g = PoppyGuide(); val says = HashSet<PoppyGuide.Say>(); var pose = g.step(dt, 0.0, 0.0, 200.0, false, emptyList(), feet(0.0), cam(0.0), ground)
        repeat(30 * 52) { pose = g.step(dt, 0.0, 0.0, 200.0, false, emptyList(), feet(0.0), cam(0.0), ground); g.say?.let { says.add(it) } }
        assertTrue(says.containsAll(listOf(PoppyGuide.Say.COME_ON, PoppyGuide.Say.YAWN, PoppyGuide.Say.ZZZ)))
        assertEquals(PoppyGuide.Act.MEDITATE, pose.act); assertEquals(PoppyGuide.Eyes.CLOSED, pose.eyes)  // sitting on her cushion, eyes closed
        var me = 0.0; repeat(30 * 2) { me += 1.4 * dt; g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground); g.say?.let { says.add(it) } }
        assertTrue(says.contains(PoppyGuide.Say.WAKE))                                 // you walk on: she wakes up
    }

    @Test fun pointsBeforeATurnAndLooksBothWaysAtTheCorner() {
        val g = PoppyGuide(); var me = 0.0; val turns = listOf(PoppyGuide.Turn(20.0, -1))
        var pointed = false; var stoppedAtCorner = false; var maxBeforeLook = 0.0; var lookedAt = -1.0; val says = HashSet<PoppyGuide.Say>()
        repeat(30 * 25) {
            me = minOf(me + 1.4 * dt, 40.0)
            val p = g.step(dt, me, 0.0, 200.0, false, turns, feet(me), cam(me), ground)
            g.say?.let { says.add(it) }
            if (p.act == PoppyGuide.Act.POINT_L && p.faceYaw > 0.5) pointed = true     // points left, head turned left
            if (lookedAt < 0) maxBeforeLook = maxOf(maxBeforeLook, g.along)
            if (g.say == PoppyGuide.Say.LOOK && lookedAt < 0) lookedAt = g.along
            if (!g.walking && kotlin.math.abs(g.along - 20.0) < 0.4) stoppedAtCorner = true
        }
        assertTrue(pointed); assertTrue(stoppedAtCorner)
        assertTrue(says.containsAll(listOf(PoppyGuide.Say.SOON_LEFT, PoppyGuide.Say.LOOK)))
        assertTrue(maxBeforeLook <= 20.05)                                            // she never crossed before looking
        assertTrue(g.along > 30)                                                       // and then went on
    }

    @Test fun runsToYouWhenYouLeaveTheRouteAndBackWhenYouReturn() {
        val g = PoppyGuide(); var me = 20.0
        repeat(30) { g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground) }
        val away = V3(20.0, 0.0, -20.0); var p = g.step(dt, me, 20.0, 200.0, false, emptyList(), away, V3(20.0, 1.45, -20.0), ground)
        repeat(30 * 6) { p = g.step(dt, me, 20.0, 200.0, false, emptyList(), away, V3(20.0, 1.45, -20.0), ground) }
        assertEquals(PoppyGuide.Mode.TO_YOU, g.mode)
        assertEquals(PoppyGuide.NEAR_YOU, kotlin.math.hypot(p.ground.x - away.x, p.ground.z - away.z), 0.4)   // a few metres from you, not in your face
        assertEquals(20.0 - PoppyGuide.NEAR_YOU, p.ground.x, 0.4)                     // on the side of the path
        repeat(30 * 8) { p = g.step(dt, me, 0.0, 200.0, false, emptyList(), feet(me), cam(me), ground) }
        assertEquals(PoppyGuide.Mode.LEAD, g.mode)
        assertEquals(0.0, p.ground.x, 0.05)                                            // back on the route
    }

    @Test fun staysOnTheRouteAndPartiesAtTheEnd() {
        val g = PoppyGuide(); var p = g.step(dt, 48.0, 0.0, 50.0, true, emptyList(), feet(48.0), cam(48.0), ground)
        val acts = HashSet<PoppyGuide.Act>()
        repeat(30 * 10) { p = g.step(dt, 48.0, 0.0, 50.0, true, emptyList(), feet(48.0), cam(48.0), ground); acts.add(p.act) }
        assertEquals(50.0, g.along, 1e-6)                                             // never past the destination
        assertTrue(acts.containsAll(listOf(PoppyGuide.Act.CHEER, PoppyGuide.Act.PIN))) // jumps for joy, then hugs the pin
        assertEquals(PoppyGuide.Eyes.HAPPY, p.eyes); assertEquals(PoppyGuide.Mouth.GRIN, p.mouth)
    }
}

class WalkSearchTest {
    @Test fun bboxReachesTheRadiusEachWay() {
        val c = LatLng(32.08, 34.82)
        val (w0, s0, e0, n0) = MapboxApi.bboxAround(c, 2500.0).split(",").map { it.toDouble() }
        assertEquals(2500.0, Geo.distance(c, LatLng(n0, c.lng)), 30.0)
        assertEquals(2500.0, Geo.distance(c, LatLng(c.lat, e0)), 30.0)
        assertTrue(w0 < c.lng && s0 < c.lat)
    }
    @Test fun parsesSearchBoxAndSortsNearestFirst() {
        val j = JSONObject("""{"type":"FeatureCollection","features":[
            {"type":"Feature","geometry":{"type":"Point","coordinates":[34.80,32.10]},"properties":{"name":"Far Cafe","mapbox_id":"a","full_address":"Far St 1","coordinates":{"latitude":32.10,"longitude":34.80}}},
            {"type":"Feature","geometry":{"type":"Point","coordinates":[34.8245,32.0822]},"properties":{"name":"קפה קרוב","mapbox_id":"b","place_formatted":"רמת גן","coordinates":{"latitude":32.0822,"longitude":34.8245}}},
            {"type":"Feature","geometry":{"type":"Point","coordinates":[34.0,32.0]},"properties":{"name":""}}]}""")
        val ps = MapboxApi.parseSearchBox(j)
        assertEquals(2, ps.size)                                                       // nameless results are dropped
        assertEquals("רמת גן", ps[1].address)
        val sorted = MapboxApi.sortByDistance(ps, LatLng(32.0820, 34.8240))
        assertEquals("קפה קרוב", sorted[0].name)
    }

    @Test fun staticMapProjectionTurnsWithYou() {
        val c = LatLng(32.0820, 34.8240); val north = LatLng(32.0830, 34.8240)
        val p0 = StaticMapProjection.project(c, c, 16.4, 0.0, 300.0, 400.0)
        assertEquals(150.0, p0[0], 1e-6); assertEquals(200.0, p0[1], 1e-6)            // the centre is the middle of the image
        val n0 = StaticMapProjection.project(north, c, 16.4, 0.0, 300.0, 400.0)
        assertEquals(150.0, n0[0], 0.5); assertTrue(n0[1] < 200 - 50)                  // north is up when you face north
        val n90 = StaticMapProjection.project(north, c, 16.4, 90.0, 300.0, 400.0)
        assertTrue(n90[0] < 150 - 50); assertEquals(200.0, n90[1], 0.5)               // facing east, north is on your left
    }

    @Test fun hebrewWords() {
        val he = Words(true); val en = Words(false)
        assertEquals("385 מ׳", he.dist(386.0)); assertEquals("1.2 ק״מ", he.dist(1200.0)); assertEquals("385 m", en.dist(386.0))
        assertEquals("4 ש׳ 12 דק׳", he.mins(252 * 60.0)); assertEquals("12 min", en.mins(720.0))
    }
}

class GroundAndSnapTest {
    @Test fun floorIsLowInTheSpreadNotTheAverage() {
        val g = GroundFinder(); val t = 1000L
        assertNull(g.estimate(t))
        listOf(-1.40, -1.41, -1.39, -1.42, -0.95, -0.90, -1.40, -1.38, -1.41, -0.85).forEach { g.add(t, it) }   // floor + a bench / bush
        assertEquals(-1.40, g.estimate(t + 100)!!, 0.03)
        assertNull(g.estimate(t + 5000))                                                // old answers expire
    }

    @Test fun snapPutsTheTrailUnderYourFeet() {
        val line = Polyline(LatLng(32.0, 34.8), listOf(LatLng(32.0, 34.8), LatLng(32.001, 34.8)))   // a line going north
        val s = SidewalkSnap(); val you = Enu(4.0, 50.0)                               // you walk 4 m east of it
        repeat(60) { s.update(you, line, 50.0, 4.0) }
        val drawn = s.apply(line.at(50.0))
        assertEquals(4.0, drawn.e, 0.05); assertEquals(line.at(50.0).n, drawn.n, 0.05) // shifted sideways only
        repeat(200) { s.update(you, line, 50.0, 40.0) }                                // far from the route: the shift fades
        assertEquals(0.0, s.e, 0.1)
    }

    @Test fun walkingStraightCorrectsTheCompass() {
        val line = Polyline(LatLng(32.0, 34.8), listOf(LatLng(32.0, 34.8), LatLng(32.001, 34.8)))   // north
        val m = MotionHeading()
        val compassSays = { _: Double, _: Double -> 30.0 }                            // the compass is 30° off
        assertNull(m.update(V3(0.0, 0.0, 0.0), 10.0, 2.0, line, compassSays))
        assertNull(m.update(V3(3.0, 0.0, 0.0), 10.5, 2.0, line, compassSays))       // progress along the route barely moved
        val r = m.update(V3(8.0, 0.0, 0.0), 11.0, 2.0, line, compassSays)!!         // walked 8 m along +x in AR
        assertEquals(8.0, r[0], 1e-9); assertEquals(0.0, r[1], 1e-9); assertEquals(0.0, r[2], 0.5)
        val a = GeoAlign(); a.heading(r[0], r[1], r[2], 1.0)
        assertEquals(PI / 2, a.yaw, 1e-6)                                              // AR +x is north
        // crossing the street (90° to the route) is not taken for a compass error
        val c = MotionHeading()
        c.update(V3(0.0, 0.0, 0.0), 20.0, 2.0, line) { _, _ -> 90.0 }
        assertNull(c.update(V3(0.0, 0.0, -8.0), 20.0, 6.0, line) { _, _ -> 90.0 })
    }

    @Test fun gpsComparesWithWhereYouWereAndOnlyCorrectsDrift() {
        val g = GpsBlend()
        for (i in 0..20) g.record(i * 100_000_000L, V3(i * 0.14, 0.0, 0.0))          // walking 1.4 m/s along +x
        assertEquals(1.4, g.camAt(1_000_000_000L)!!.x, 1e-9)                          // where you were 1 s in
        assertNull(GpsBlend().camAt(5L))
        assertTrue(g.gain(1_000_000_000L, 5.0, 2.0, settled = true) < 0.08)           // a good fix: a small slow nudge
        assertEquals(0.0, g.gain(2_000_000_000L, 30.0, 2.0, settled = true), 1e-9)    // a rough fix: ignored
        assertEquals(0.0, g.gain(3_000_000_000L, 5.0, 60.0, settled = true), 1e-9)    // far from AR: ignored …
        g.gain(4_000_000_000L, 5.0, 60.0, settled = true); g.gain(5_000_000_000L, 5.0, 60.0, settled = true)
        assertTrue(g.gain(6_000_000_000L, 5.0, 60.0, settled = true) > 0.0)           // … unless it keeps saying so
    }
}

class RibbonShapeTest {
    private val L = Polyline(LatLng(32.0, 34.8), listOf(LatLng(32.0, 34.8), LatLng(32.0002, 34.8), LatLng(32.0002, 34.79976)))   // ~22 m north, then ~22 m west

    @Test fun roundedCornerIsSmoothAndKeepsDistances() {
        val r = RoundedRoute(L)
        assertEquals(L.length, r.along.last(), 1e-9)
        val corner = L.cum[1]
        val c = r.at(corner); val sharp = L.at(corner)
        assertTrue(kotlin.math.hypot(c.e - sharp.e, c.n - sharp.n) > 0.4)              // the corner is cut round
        var prev = r.dir(1.0)
        var s = 1.0
        while (s < L.length - 1) { val d = r.dir(s); assertTrue(d.e * prev.e + d.n * prev.n > 0.9); prev = d; s += 0.5 }   // no kinks
        assertEquals(L.at(5.0).n, r.at(5.0).n, 1e-6)                                  // straight parts unchanged
    }

    @Test fun sectionsHaveConstantWidthFadeAtBothEndsAndFixedCount() {
        val r = RoundedRoute(L)
        val secs = RibbonShape.sections(r, 2.3, 30.0, 0.85, 2.4, 8.0, 0.5, 110)
        assertEquals(110, secs.size)
        for (sc in secs) assertEquals(0.85, kotlin.math.hypot(sc.left.e - sc.right.e, sc.left.n - sc.right.n), 1e-6)
        assertEquals(0.0, secs.first().v, 1e-9)
        assertEquals(1.0, secs.last().v, 1e-9)
        assertTrue(secs.count { it.v == 0.5 } > 20)                                    // the full part in the middle
        // walking 0.2 m on: the grid sections stay put on the street
        val later = RibbonShape.sections(r, 2.5, 30.2, 0.85, 2.4, 8.0, 0.5, 110)
        val a = secs[10].left; assertTrue(later.any { kotlin.math.hypot(it.left.e - a.e, it.left.n - a.n) < 1e-6 })
    }

    @Test fun textureIsSymmetricAndSolidInTheMiddle() {
        val w = 32; val h = 128; val px = RibbonShape.texture(w, h)
        val mid = px[(h / 2) * w + w / 2]
        assertEquals((RibbonShape.BODY * 255).toInt(), mid ushr 24)
        assertTrue((px[w / 2] ushr 24) < 10 && (px[(h - 1) * w + w / 2] ushr 24) < 10)  // both ends see-through
    }
}

class MoneyTest {
    @Test fun currenciesThatMatterWhereYouAre() {
        assertEquals(listOf("ILS" to "THB", "USD" to "THB"), Money.pairs("ILS", "THB"))     // abroad: yours and dollars into baht
        assertEquals(listOf("USD" to "ILS", "EUR" to "ILS"), Money.pairs("ILS", "ILS"))     // at home: dollars and euros
        assertEquals(listOf("USD" to "ILS", "EUR" to "ILS"), Money.pairs("ILS", null))
        assertEquals(listOf("USD" to "THB"), Money.pairs("USD", "THB"))                      // no pair twice
    }
    @Test fun theBoardAgainstTheMarket() {
        assertEquals(0, Money.judge(32.0, 32.4).second)                                   // 1.2% under: good
        assertEquals(1, Money.judge(31.3, 32.4).second)                                   // 3.4% under: fair
        assertEquals(2, Money.judge(30.5, 32.4).second)                                   // 5.9% under: expensive
        assertEquals(0, Money.judge(32.6, 32.4).second)                                   // over the market: good
        assertEquals(-0.0123, Money.judge(32.0, 32.4).first, 1e-3)
        val m = Money.Market("ILS", "THB", mapOf(("ILS" to "THB") to 8.9, ("USD" to "THB") to 32.4, ("EUR" to "THB") to 35.1))
        assertEquals(listOf("ILS" to "THB", "USD" to "THB"), m.main)
        assertEquals(listOf("USD" to "THB", "EUR" to "THB"), m.board)
    }
}

class SurfaceTest {
    @Test fun profileInterpolatesAndKeepsNearFloor() {
        val g = GroundProfile()
        assertEquals(-1.4, g.heightAt(10.0, -1.4, 0.0), 1e-9)
        g.observe(10.0, -1.0, 0); g.observe(14.0, -0.6, 0)
        assertEquals(-1.4, g.heightAt(1.0, -1.4, 0.0), 1e-9)
        val h = g.heightAt(12.0, -1.4, 0.0); assertTrue(h > -1.0 && h < -0.6)
        val far = g.heightAt(30.0, -1.4, 0.0); assertTrue(far >= -0.6 && far <= -0.6 + 0.15 * GroundProfile.CARRY * 0.6 + 1e-9)
    }
    @Test fun profileNeedsAnOutlierThreeTimes() {
        val o = GroundProfile(); repeat(5) { o.observe(20.0, -1.4, 0) }
        o.observe(20.0, -0.4, 1); o.observe(20.0, -0.4, 2)
        assertEquals(-1.4, o.heightAt(20.0, -1.4, 0.0), 0.01)
        o.observe(20.0, -0.4, 3)
        assertEquals(-0.4, o.heightAt(20.0, -1.4, 0.0), 0.01)
    }
    @Test fun confidenceWaitsAndEases() {
        val c = SurfaceConfidence(); var t = 0L
        fun run(ms: Long, tracking: Boolean, ago: Long, hits: Int, spread: Double, offset: Double = 0.0): SurfaceConfidence.State {
            var s = c.state; val end = t + ms; while (t < end) { t += 33; s = c.update(t, tracking, ago, hits, spread, false, offset) }; return s
        }
        assertEquals(SurfaceConfidence.State.LOST, run(500, true, 100, 6, 0.05))
        assertEquals(SurfaceConfidence.State.GOOD, run(700, true, 100, 6, 0.05))
        run(600, true, 100, 6, 0.05); assertTrue(c.shown > 0.8)
        assertEquals(SurfaceConfidence.State.GOOD, run(1500, true, 3000, 0, 9.0))
        assertEquals(SurfaceConfidence.State.PARTIAL, run(1000, true, 3000, 0, 9.0))
        assertTrue(c.reach(48.0) <= SurfaceConfidence.PARTIAL_REACH)
        assertEquals(SurfaceConfidence.State.LOST, run(3500, true, 9000, 0, 9.0)); assertTrue(c.shown < 0.05)
        assertEquals(SurfaceConfidence.State.GOOD, run(1200, true, 100, 6, 0.05))
        assertEquals(SurfaceConfidence.State.LOST, run(3000, true, 3000, 0, 9.0, offset = 40.0))
        assertNotEquals(SurfaceConfidence.State.BROKEN, run(300, false, 0, 0, 0.0))
        assertEquals(SurfaceConfidence.State.BROKEN, run(400, false, 0, 0, 0.0))
    }
}

class SidewalkTest {
    private val o = LatLng(32.08, 34.78)
    private fun ll(e: Double, n: Double) = Geo.fromEnu(o, Enu(e, n))
    // north 100 m then east 100 m (a right turn) on a street; sidewalks 6 m either side
    private val mid get() = Polyline(o, listOf(ll(0.0, 0.0), ll(0.0, 100.0), ll(100.0, 100.0)))
    private val road = StreetData.Way("street", listOf(Enu(0.0, -20.0), Enu(0.0, 100.0), Enu(120.0, 100.0)))
    private val swE = StreetData.Way("sidewalk", listOf(Enu(6.0, -20.0), Enu(6.0, 94.0), Enu(120.0, 94.0)))
    private val swW = StreetData.Way("sidewalk", listOf(Enu(-6.0, -20.0), Enu(-6.0, 106.0), Enu(120.0, 106.0)))

    @Test fun trailGoesOnTheMapsSidewalkWithRealCorners() {
        val plan = SidewalkPlan.build(mid, StreetData(listOf(swE, swW), listOf(swE, swW), listOf(road), emptyList()))
        assertTrue(plan.mapped(-1) > 0.85)
        val right = WalkLine(mid, plan.lateral(-1))
        val p = right.line.at(right.toWalk(50.0)); assertEquals(6.0, p.e, 0.2); assertEquals(50.0, p.n, 0.5)
        assertTrue(right.line.pts.any { Math.hypot(it.e - 6, it.n - 94) < 0.3 })          // inside corner
        val q = right.line.at(right.toWalk(150.0)); assertEquals(94.0, q.n, 0.2)
        assertEquals(150.0, right.toMiddle(right.toWalk(150.0)), 1e-6)
        val left = WalkLine(mid, plan.lateral(1))
        assertTrue(left.line.pts.any { Math.hypot(it.e + 6, it.n - 106) < 0.3 })         // outside corner, over the crossing
    }
    @Test fun withoutMappedSidewalksBesideTheRoadButNotInABuilding() {
        val bld = listOf(Enu(5.0, 20.0), Enu(15.0, 20.0), Enu(15.0, 40.0), Enu(5.0, 40.0), Enu(5.0, 20.0))
        val plan = SidewalkPlan.build(mid, StreetData(emptyList(), emptyList(), listOf(road), listOf(bld)))
        assertEquals(6.0, plan.right[5], 0.01); assertEquals(1, plan.rightHow[5])
        assertTrue(plan.right[15] < 5.0 && plan.right[15] > 4.0)
    }
    @Test fun aRouteOnAFootpathStaysOnIt() {
        val path = StreetData.Way("footway", listOf(Enu(0.0, -10.0), Enu(0.0, 100.0), Enu(110.0, 100.0)))
        val plan = SidewalkPlan.build(mid, StreetData(listOf(path), listOf(path), emptyList(), emptyList()))
        assertTrue(plan.walkShare() > 0.95)
        assertEquals(mid.length, WalkLine(mid, plan.lateral(-1)).line.length, 0.01)
    }
    @Test fun readsVectorTiles() {
        fun vint(o: java.io.ByteArrayOutputStream, v0: Long) { var v = v0; while (true) { if (v and 0x7fL.inv() == 0L) { o.write(v.toInt()); return }; o.write(((v and 0x7f) or 0x80).toInt()); v = v ushr 7 } }
        fun field(o: java.io.ByteArrayOutputStream, f: Int, b: ByteArray) { vint(o, ((f shl 3) or 2).toLong()); vint(o, b.size.toLong()); o.write(b) }
        fun packed(xs: List<Int>) = java.io.ByteArrayOutputStream().also { o -> xs.forEach { vint(o, it.toLong() and 0xffffffffL) } }.toByteArray()
        fun zz(n: Int) = (n shl 1) xor (n shr 31)
        fun bytes(f: (java.io.ByteArrayOutputStream) -> Unit) = java.io.ByteArrayOutputStream().also(f).toByteArray()
        val feat = bytes { field(it, 2, packed(listOf(0, 0, 1, 1))); vint(it, 24); vint(it, 2); field(it, 4, packed(listOf(9, zz(0), zz(0), 10, zz(2048), zz(4096)))) }
        val layer = bytes { field(it, 1, "road".toByteArray()); field(it, 2, feat); field(it, 3, "class".toByteArray()); field(it, 3, "type".toByteArray())
            field(it, 4, bytes { v -> field(v, 1, "path".toByteArray()) }); field(it, 4, bytes { v -> field(v, 1, "sidewalk".toByteArray()) }); vint(it, 40); vint(it, 4096) }
        val tile = bytes { field(it, 3, layer) }
        val gz = bytes { java.util.zip.GZIPOutputStream(it).use { g -> g.write(tile) } }
        val f = Mvt.decode(gz, setOf("road")).single()
        assertEquals("sidewalk", f.props["type"]); assertEquals(2, f.type)
        assertEquals(0.5, f.parts[0][1][0], 1e-9); assertEquals(1.0, f.parts[0][1][1], 1e-9)
        val t = Mvt.tileOf(LatLng(32.08, 34.78), 16)
        assertTrue(Geo.distance(Mvt.place(16, t[0], t[1], 0.5, 0.5), LatLng(32.08, 34.78)) < 400)
    }
}

class EnglishTest {
    @Test fun hebrewNamesInEnglishLetters() {
        assertEquals("Ben Yehoda", HebrewLatin.spell("בן יהודה"))
        assertEquals("Arlozorov", HebrewLatin.spell("ארלוזורוב"))
        assertEquals("Turn left onto Dizengoff Street", HebrewLatin.english("Turn left onto דיזנגוף", mapOf("דיזנגוף" to "Dizengoff Street")))
        assertFalse(HebrewLatin.has(HebrewLatin.english("Head north on אבן גבירול")))
        assertEquals("Turn right", HebrewLatin.english("Turn right"))
    }
}

class SceneLabelsTest {
    @Test fun onlyWalkableSurfacesCount() {
        assertEquals(true, SceneLabels.judge(SceneLabels.SIDEWALK to 200))
        assertEquals(true, SceneLabels.judge(SceneLabels.ROAD to 60))
        assertEquals(true, SceneLabels.judge(SceneLabels.TERRAIN to 150))
        assertEquals(false, SceneLabels.judge(SceneLabels.STRUCTURE to 200))      // a fence, a wall
        assertEquals(false, SceneLabels.judge(SceneLabels.BUILDING to 180))       // a window sill
        assertNull(SceneLabels.judge(SceneLabels.OBJECT to 40))                   // unsure: not trusted
        assertNull(SceneLabels.judge(SceneLabels.UNLABELED to 255))
        assertNull(SceneLabels.judge(null))
    }
    @Test fun indoorsHidesTheTrail() {
        val c = SurfaceConfidence(); var t = 0L
        repeat(60) { t += 33; c.update(t, true, 100, 6, 0.05, false, 0.0) }
        assertEquals(SurfaceConfidence.State.GOOD, c.state)
        repeat(90) { t += 33; c.update(t, true, 100, 6, 0.05, false, 0.0, indoor = true) }
        assertEquals(SurfaceConfidence.State.LOST, c.state)
    }
}
