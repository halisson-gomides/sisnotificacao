// Utilitários globais
window.NotificationUtils = (function() {
    function supported() {
        return 'Notification' in window;
    }

    function isGranted() {
        return supported() && Notification.permission === 'granted';
    }

    function isDefault() {
        return supported() && Notification.permission === 'default';
    }

    // Sempre chamar esta função dentro de um evento de clique/gesto do usuário
    function requestByUserGesture() {
        
        if (!supported()) return Promise.resolve('unsupported');

        if (!isDefault()) {
            // already granted or denied
            return Promise.resolve(Notification.permission);
        }

        try {
            const result = Notification.requestPermission();
            // Alguns browsers retornam Promise, outros usam callback
            if (result && typeof result.then === 'function') {
                return result;
            }
            return new Promise(resolve => {
                Notification.requestPermission(perm => resolve(perm));
            });
        } catch (e) {
            return Promise.reject(e);
        }
    }

    function showBrowserNotification(title, body, options = {}) {
        if (!supported()) return;
        if (Notification.permission !== 'granted') return;
        new Notification(title, {
            body: body,
            icon: options.icon || '/static/notification-icon.png',
            ...options
        });
    }

    return {
        supported,
        isGranted,
        isDefault,
        requestByUserGesture,
        showBrowserNotification
    };
})();