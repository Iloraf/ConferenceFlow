self.addEventListener("push", function(event) {
  let data = {};
  try {
    data = event.data.json();
  } catch (e) {
    console.error("Push data error", e);
  }
  const options = {
    body: data.body || "Notification",
    icon: "/static/icons/icon-192x192.png",
    data: { url: data.url || "/" }
  };
  event.waitUntil(
    self.registration.showNotification(data.title || "Info", options)
  );
});

self.addEventListener("notificationclick", function(event) {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
