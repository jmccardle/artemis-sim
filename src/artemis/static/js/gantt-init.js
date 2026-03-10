/* Gantt chart initialization using Frappe Gantt */

function initGantt() {
    var dataEl = document.getElementById('gantt-data');
    var chartEl = document.getElementById('gantt-chart');

    if (!dataEl || !chartEl || typeof Gantt === 'undefined') return;

    try {
        var tasks = JSON.parse(dataEl.textContent);
        if (!tasks || tasks.length === 0) {
            chartEl.innerHTML = '<div class="text-muted text-center py-4">No tasks to display in timeline</div>';
            return;
        }

        // Ensure valid date ranges
        tasks = tasks.map(function(t) {
            if (t.start === t.end) {
                var d = new Date(t.end);
                d.setDate(d.getDate() + 1);
                t.end = d.toISOString().split('T')[0];
            }
            return t;
        });

        new Gantt('#gantt-chart', tasks, {
            view_mode: 'Day',
            bar_height: 24,
            padding: 18,
            on_click: function(task) {
                openTaskModal(task.id);
            }
        });
    } catch (e) {
        chartEl.innerHTML = '<div class="text-muted text-center py-4">Error loading timeline</div>';
    }
}

// Init on page load
document.addEventListener('DOMContentLoaded', initGantt);

// Re-init after HTMX swaps
document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.querySelector('#gantt-data') || evt.detail.target.id === 'gantt-chart') {
        initGantt();
    }
});
