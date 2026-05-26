--- providers/runway_video_provider.py
+++ providers/runway_video_provider.py
@@ -186,3 +186,11 @@
     retries=3
 ):
     pass
+
+
+
+def timeout_wrapper(
+    operation,
+    timeout_seconds=60
+):
+    return operation()