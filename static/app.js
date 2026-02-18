// CA New Grad RN Tracker — Client-side JS

// Toast notification
function showToast(message) {
    let toast = document.querySelector('.toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
}

// Status → row class mapping
const statusClasses = {
    'Not Started': '',
    'In Progress': 'row-in-progress',
    'Submitted': 'row-submitted',
    'Interview': 'row-interview',
    'Offer': 'row-offer',
    'Rejected': 'row-rejected'
};

function applyRowStatus(row, status) {
    Object.values(statusClasses).forEach(function (cls) {
        if (cls) row.classList.remove(cls);
    });
    if (statusClasses[status]) {
        row.classList.add(statusClasses[status]);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    // Apply initial row colors based on current status
    document.querySelectorAll('.status-select').forEach(function (select) {
        var row = select.closest('tr');
        if (row) applyRowStatus(row, select.value);
    });

    // Status dropdowns — save + color row
    document.querySelectorAll('.status-select').forEach(function (select) {
        select.addEventListener('change', function () {
            var id = this.dataset.id;
            var newStatus = this.value;
            var row = this.closest('tr');

            fetch('/api/programs/' + id, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ application_status: newStatus })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data.success) {
                        showToast('Status updated: ' + newStatus);
                        if (row) applyRowStatus(row, newStatus);
                    } else {
                        showToast('Error: ' + (data.error || 'Update failed'));
                    }
                })
                .catch(function () {
                    showToast('Error: Could not save');
                });
        });
    });

    // Select all checkbox (programs page)
    var selectAll = document.getElementById('select-all');
    if (selectAll) {
        selectAll.addEventListener('change', function () {
            var checked = this.checked;
            // Only toggle visible (not hidden) rows
            document.querySelectorAll('.sheet tbody tr:not([style*="display: none"]) .compare-check').forEach(function (cb) {
                cb.checked = checked;
            });
            updateCompareBtn();
        });
    }

    // Individual compare checkboxes
    document.querySelectorAll('.compare-check').forEach(function (cb) {
        cb.addEventListener('change', updateCompareBtn);
    });

    // Client-side instant search
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function () {
            filterTable();
        }, 150));
    }

    // Client-side instant filter dropdowns
    document.querySelectorAll('.sheet-filters select[data-instant]').forEach(function (sel) {
        sel.addEventListener('change', function () {
            filterTable();
        });
    });

    // Keyboard shortcut: / to focus search
    document.addEventListener('keydown', function (e) {
        if (e.key === '/' && !isEditing(e.target)) {
            var si = document.querySelector('.sheet-filters input[type="search"]');
            if (si) {
                e.preventDefault();
                si.focus();
                si.select();
            }
        }
        // Escape to blur search
        if (e.key === 'Escape') {
            document.activeElement.blur();
        }
    });

    // Auto-save notes with debounce (detail page)
    var notesArea = document.getElementById('personal-notes');
    if (notesArea) {
        notesArea.addEventListener('input', debounce(function () {
            var programId = notesArea.dataset.id;
            if (programId) {
                saveNotes(parseInt(programId));
            }
        }, 1000));
    }

    // Deadline urgency highlights
    highlightDeadlines();
});

function debounce(fn, ms) {
    var timer;
    return function () {
        clearTimeout(timer);
        timer = setTimeout(fn, ms);
    };
}

function isEditing(el) {
    var tag = el.tagName.toLowerCase();
    return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
}

// ===== Client-side filtering =====

function filterTable() {
    var searchInput = document.querySelector('.sheet-filters input[type="search"]');
    var regionSelect = document.querySelector('.sheet-filters select[data-instant="region"]');
    var citySelect = document.querySelector('.sheet-filters select[data-instant="city"]');
    var bsnSelect = document.querySelector('.sheet-filters select[data-instant="bsn"]');
    var statusSelect = document.querySelector('.sheet-filters select[data-instant="status"]');

    var cohortStatusSelect = document.querySelector('.sheet-filters select[data-instant="cohort-status"]');

    var query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var region = regionSelect ? regionSelect.value : '';
    var city = citySelect ? citySelect.value : '';
    var bsn = bsnSelect ? bsnSelect.value : '';
    var status = statusSelect ? statusSelect.value : '';
    var cohortStatus = cohortStatusSelect ? cohortStatusSelect.value : '';

    var rows = document.querySelectorAll('.sheet tbody tr');
    var visibleCount = 0;

    rows.forEach(function (row) {
        var show = true;

        // Text search — match against all cell text
        if (query) {
            var text = row.textContent.toLowerCase();
            if (text.indexOf(query) === -1) show = false;
        }

        // Region filter
        if (show && region) {
            var regionCell = row.querySelector('.col-region');
            if (regionCell && regionCell.textContent.trim() !== region) show = false;
        }

        // City filter
        if (show && city) {
            var cityCell = row.querySelector('.col-city');
            if (cityCell && cityCell.textContent.trim() !== city) show = false;
        }

        // BSN filter
        if (show && bsn) {
            var bsnCell = row.querySelector('.col-bsn');
            if (bsnCell) {
                var bsnText = bsnCell.textContent.trim().toLowerCase();
                if (bsn === 'no' && bsnText === 'req') show = false;
                if (bsn === 'yes' && bsnText !== 'req') show = false;
            }
        }

        // Status filter
        if (show && status) {
            var statusSel = row.querySelector('.status-select');
            if (statusSel && statusSel.value !== status) show = false;
        }

        // Cohort status filter (released / not released / rolling / paused)
        if (show && cohortStatus) {
            var dateCells = row.querySelectorAll('.col-date');
            var cohortCell = dateCells.length >= 3 ? dateCells[2] : null;
            var cohortText = cohortCell ? cohortCell.textContent.trim().toLowerCase() : '';
            var isDate = /^\d{4}-\d{2}-\d{2}/.test(cohortText);

            if (cohortStatus === 'released' && !isDate) show = false;
            if (cohortStatus === 'not-released' && (isDate || cohortText.indexOf('rolling') !== -1 || cohortText.indexOf('paused') !== -1)) show = false;
            if (cohortStatus === 'rolling' && cohortText.indexOf('rolling') === -1) show = false;
            if (cohortStatus === 'paused' && cohortText.indexOf('paused') === -1) show = false;
        }

        row.style.display = show ? '' : 'none';
        if (show) visibleCount++;
    });

    // Update count
    var countEl = document.querySelector('.sheet-count');
    if (countEl) {
        countEl.textContent = visibleCount + ' of ' + rows.length + ' rows';
    }
}

// ===== Deadline urgency =====

function highlightDeadlines() {
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    document.querySelectorAll('.sheet tbody tr').forEach(function (row) {
        var dateCells = row.querySelectorAll('.col-date');
        // App Close is the second .col-date (index 1 after App Open)
        // In our table: App Open (index 0), App Close (index 1), Cohort (index 2)
        if (dateCells.length >= 2) {
            var closeCell = dateCells[1];
            var dateStr = closeCell.textContent.trim();
            if (dateStr) {
                var closeDate = parseDate(dateStr);
                if (closeDate) {
                    var daysLeft = Math.ceil((closeDate - today) / (1000 * 60 * 60 * 24));
                    if (daysLeft < 0) {
                        // Past deadline
                        closeCell.innerHTML = dateStr + ' <span class="deadline-past">closed</span>';
                    } else if (daysLeft <= 7) {
                        closeCell.innerHTML = dateStr + ' <span class="deadline-urgent">' + daysLeft + 'd</span>';
                        row.classList.add('urgent-row');
                    } else if (daysLeft <= 14) {
                        closeCell.innerHTML = dateStr + ' <span class="deadline-warning">' + daysLeft + 'd</span>';
                        row.classList.add('warning-row');
                    } else if (daysLeft <= 30) {
                        closeCell.innerHTML = dateStr + ' <span class="deadline-soon">' + daysLeft + 'd</span>';
                    }
                }
            }

            // Check if app is currently open
            var openCell = dateCells[0];
            var openStr = openCell.textContent.trim();
            if (openStr && dateStr) {
                var openDate = parseDate(openStr);
                var closeDate2 = parseDate(dateStr);
                if (openDate && closeDate2 && openDate <= today && closeDate2 >= today) {
                    openCell.innerHTML = openStr + ' <span class="badge-open">OPEN</span>';
                }
            }
        }
    });
}

function parseDate(str) {
    if (!str) return null;
    // Handle YYYY-MM-DD
    var parts = str.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (parts) {
        return new Date(parseInt(parts[1]), parseInt(parts[2]) - 1, parseInt(parts[3]));
    }
    // Handle MM/DD/YYYY
    parts = str.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (parts) {
        return new Date(parseInt(parts[3]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    }
    return null;
}

// ===== Compare =====

function updateCompareBtn() {
    var btn = document.getElementById('compare-btn');
    if (!btn) return;
    var checked = document.querySelectorAll('.compare-check:checked');
    btn.disabled = checked.length < 2;
    if (checked.length >= 2) {
        btn.textContent = 'Compare ' + checked.length;
    } else {
        btn.textContent = 'Compare';
    }
}

function goCompare() {
    var ids = [];
    document.querySelectorAll('.compare-check:checked').forEach(function (cb) {
        ids.push(cb.value);
    });
    if (ids.length >= 2) {
        window.location.href = '/compare?ids=' + ids.join(',');
    }
}

// ===== Notes (detail page) =====

function saveNotes(programId) {
    var textarea = document.getElementById('personal-notes');
    if (!textarea) return;

    fetch('/api/programs/' + programId, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personal_notes: textarea.value })
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                showToast('Notes saved');
            } else {
                showToast('Error saving notes');
            }
        })
        .catch(function () {
            showToast('Error: Could not save');
        });
}

// ===== CSV Export =====

function exportCSV() {
    window.location.href = '/api/export/csv';
}
