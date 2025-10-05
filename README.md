# SerpApi → WooCommerce Sync (GitHub Actions)

مشروع مجاني لتحديث منتجات WooCommerce تلقائيًا بالمنتجات التريندينغ من Amazon عبر SerpApi.

## كيفية الاستخدام

1. أنشئ Repository على GitHub.
2. ارفع كل الملفات إليه.
3. أضف Secrets:
   - `SERPAPI_KEY` → مفتاح SerpApi
   - `WC_BASE` → رابط متجرك WooCommerce
   - `WC_KEY` → WooCommerce Consumer Key
   - `WC_SECRET` → WooCommerce Consumer Secret
4. GitHub Actions سيشغل السكربت تلقائيًا حسب الجدول (كل يوم الساعة 03:00 UTC).
5. يمكن تشغيل Workflow يدويًا من GitHub UI (Actions → SerpApi Woo Sync → Run workflow).

> ملاحظة: الصور والروابط يتم سحبها مباشرة من Amazon. راجع حقوق الاستخدام وسياسة WooCommerce إذا لزم.
