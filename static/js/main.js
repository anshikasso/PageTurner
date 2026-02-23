// Auto-dismiss flash messages
document.addEventListener('DOMContentLoaded', function() {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(f => {
        setTimeout(() => f.remove(), 5000);
    });

    // Active nav link highlight
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
});

// Confirm dialogs
function confirmDelete(msg) {
    return confirm(msg || 'Are you sure you want to delete this record?');
}
