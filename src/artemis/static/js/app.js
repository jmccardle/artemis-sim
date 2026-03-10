/* Artemis Mission Simulation — App JS */

// HTMX configuration
document.body.addEventListener('htmx:configRequest', function(evt) {
    // Add CSRF or session headers if needed
});

// Re-initialize Bootstrap components after HTMX swaps
document.body.addEventListener('htmx:afterSwap', function(evt) {
    // Initialize tooltips
    var tooltips = evt.detail.target.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(function(el) {
        new bootstrap.Tooltip(el);
    });

    // Initialize popovers
    var popovers = evt.detail.target.querySelectorAll('[data-bs-toggle="popover"]');
    popovers.forEach(function(el) {
        new bootstrap.Popover(el);
    });
});

// Show toast notifications from SSE events
function showToast(message, type) {
    type = type || 'info';
    var bgClass = {
        'success': 'bg-success',
        'error': 'bg-danger',
        'warning': 'bg-warning text-dark',
        'info': 'bg-info text-dark'
    }[type] || 'bg-info text-dark';

    var toastHtml = '<div class="toast align-items-center text-white ' + bgClass + ' border-0" role="alert">' +
        '<div class="d-flex">' +
        '<div class="toast-body">' + message + '</div>' +
        '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>' +
        '</div></div>';

    var container = document.getElementById('toast-container');
    if (container) {
        container.insertAdjacentHTML('beforeend', toastHtml);
        var toastEl = container.lastElementChild;
        var toast = new bootstrap.Toast(toastEl, { delay: 5000 });
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', function() {
            toastEl.remove();
        });
    }
}

// Handle SSE notification events
document.body.addEventListener('sse:notification', function(evt) {
    try {
        var data = JSON.parse(evt.detail.data);
        showToast(data.message, data.type);
    } catch (e) {
        // Ignore parse errors
    }
});

// Open task detail modal
function openTaskModal(taskId) {
    fetch('/views/tasks/' + taskId + '/detail')
        .then(function(response) { return response.text(); })
        .then(function(html) {
            var container = document.getElementById('modal-container');
            container.innerHTML = html;
            var modalEl = container.querySelector('.modal');
            if (modalEl) {
                var modal = new bootstrap.Modal(modalEl);
                modal.show();
            }
        });
}

// Confirm action with Bootstrap modal
function confirmAction(message, onConfirm) {
    if (confirm(message)) {
        onConfirm();
    }
}
