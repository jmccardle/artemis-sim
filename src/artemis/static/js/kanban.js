/* Kanban board — click-to-move task status transitions */

document.addEventListener('DOMContentLoaded', function() {
    // HTML5 drag and drop (optional enhancement)
    var cards = document.querySelectorAll('.kanban-card');
    var columns = document.querySelectorAll('.kanban-column');

    cards.forEach(function(card) {
        card.setAttribute('draggable', 'true');

        card.addEventListener('dragstart', function(e) {
            e.dataTransfer.setData('text/plain', card.dataset.taskId || '');
            card.classList.add('dragging');
        });

        card.addEventListener('dragend', function() {
            card.classList.remove('dragging');
        });
    });

    columns.forEach(function(column) {
        column.addEventListener('dragover', function(e) {
            e.preventDefault();
            column.classList.add('drag-over');
        });

        column.addEventListener('dragleave', function() {
            column.classList.remove('drag-over');
        });

        column.addEventListener('drop', function(e) {
            e.preventDefault();
            column.classList.remove('drag-over');
            // Drop handling would require an HTMX call to update task status
            // For now, use the button-based approach
        });
    });
});
