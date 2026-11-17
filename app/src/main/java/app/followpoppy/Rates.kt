package app.followpoppy

import android.content.Context
import android.location.Geocoder
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Currency
import java.util.Locale

/**
 * Money for the "exchange" kind: the market rate of the day (to compare with what a money changer's board says), the
 * currencies that matter where you are, and where a changer publishes its own rates.
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

    /**
     * Where to see this changer's own rates: chains that publish theirs get their site; any other changer gets a web
     * search for its name and "exchange rate" (its own page or listing usually comes first).
     */
    fun ratesPage(place: Place): String {
        val n = place.name.lowercase(Locale.ROOT)
        CHAINS.firstOrNull { (keys, _) -> keys.any { it in n } }?.let { return it.second }
        return "https://www.google.com/search?q=" + URLEncoder.encode("${place.name} ${place.address} exchange rate today", "UTF-8")
    }
    private val CHAINS = listOf(
        listOf("superrich", "super rich", "ซุปเปอร์ริช") to "https://www.superrichthailand.com/#!/en/exchange",
    )

    private fun get(url: String): JSONObject {
        val c = URL(url).openConnection() as HttpURLConnection
        c.connectTimeout = 5_000; c.readTimeout = 6_000
        try { return JSONObject(c.inputStream.bufferedReader().readText()) } finally { c.disconnect() }
    }
}
