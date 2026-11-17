package app.followpoppy

import android.content.Context
import android.location.Geocoder
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Currency
import java.util.Locale

/**
 * Money for the "exchange" kind: the market rate of the day (to compare with what a money changer's board says) and
 * the currencies that matter where you are. (Money changers do not publish their rates anywhere an app can read them.)
 */
internal object Money {
    /** The currency of the country at [at] (Android's geocoder), or null when it cannot tell. Call off the main thread. */
    fun localCurrency(context: Context, at: LatLng): String? = runCatching {
        @Suppress("DEPRECATION")
        val cc = Geocoder(context, Locale.ENGLISH).getFromLocation(at.lat, at.lng, 1)?.firstOrNull()?.countryCode
        cc?.let { Currency.getInstance(Locale("", it)).currencyCode }
    }.getOrNull()

    /** Your own currency (the phone's region), shekels when it cannot tell. */
    fun homeCurrency(): String = runCatching { Currency.getInstance(Locale.getDefault()).currencyCode }.getOrNull()
        ?.takeIf { it != "XXX" } ?: "ILS"

    /**
     * What you would pay attention to at a changer here: (from, to) pairs. Abroad: your currency and dollars into the
     * local one; at home: dollars and euros into yours.
     */
    fun pairs(home: String, local: String?): List<Pair<String, String>> =
        if (local == null || local == home) listOf("USD" to home, "EUR" to home)
        else listOf(home to local, "USD" to local).distinct().filter { it.first != it.second }

    /**
     * Market rates (1 [base] = x of each symbol): the European Central Bank's daily rates (Frankfurter); for a currency
     * the ECB does not publish, the open ExchangeRate-API. Call off the main thread.
     */
    fun rates(base: String, symbols: Set<String>): Map<String, Double> {
        val out = HashMap<String, Double>()
        runCatching {
            val j = get("https://api.frankfurter.dev/v1/latest?base=$base&symbols=${symbols.joinToString(",")}").getJSONObject("rates")
            for (k in j.keys()) out[k] = j.getDouble(k)
        }
        if (symbols.any { it !in out && it != base }) runCatching {
            val j = get("https://open.er-api.com/v6/latest/$base").getJSONObject("rates")
            for (s in symbols) if (s !in out && j.has(s)) out[s] = j.getDouble(s)
        }
        if (base in symbols) out[base] = 1.0
        return out
    }

    /** A currency's sign (₪, $, ฿ …), or its code when there is none. */
    fun sign(code: String): String = runCatching { Currency.getInstance(code).getSymbol(Locale.US) }.getOrNull()
        ?.let { if (it == code) KNOWN[code] ?: code else it } ?: code
    private val KNOWN = mapOf("ILS" to "₪", "THB" to "฿", "USD" to "$", "EUR" to "€", "GBP" to "£", "JPY" to "¥", "INR" to "₹", "TRY" to "₺", "VND" to "₫", "KRW" to "₩", "PHP" to "₱")

    /** Market rates where you are: your currency, the local one, and 1 from = x to for each pair that matters. */
    class Market(val home: String, val local: String, val rate: Map<Pair<String, String>, Double>) {
        /** The pairs for the card: abroad yours and dollars into the local currency, at home dollars and euros. */
        val main get() = pairs(home, local).filter { it in rate }
        /** Dollars and euros into the local currency (what a changer's board shows). */
        val board get() = listOf("USD" to local, "EUR" to local).filter { it.first != it.second && it in rate }
    }

    /** Everything the money screens need, for where you are. Call off the main thread. */
    fun market(context: Context, at: LatLng): Market {
        val home = homeCurrency(); val local = localCurrency(context, at) ?: home
        val want = (pairs(home, local) + listOf("USD" to local, "EUR" to local)).filter { it.first != it.second }.distinct()
        val rate = HashMap<Pair<String, String>, Double>()
        for ((from, ps) in want.groupBy { it.first }) {
            val r = rates(from, ps.map { it.second }.toSet())
            for (p in ps) r[p.second]?.let { rate[p] = it }
        }
        return Market(home, local, rate)
    }

    /**
     * How a changer's board compares with the market: the board says 1 [from] = [board] local, the market [market].
     * Returns the difference (negative = you get less) and a verdict: 0 good (within 2%), 1 fair (2-4%), 2 expensive.
     */
    fun judge(board: Double, market: Double): Pair<Double, Int> {
        val d = board / market - 1
        return d to when { d >= -0.02 -> 0; d >= -0.04 -> 1; else -> 2 }
    }

    private fun get(url: String): JSONObject {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 5_000; c.readTimeout = 6_000
        try { return JSONObject(c.inputStream.bufferedReader().readText()) } finally { c.disconnect() }
    }
}
