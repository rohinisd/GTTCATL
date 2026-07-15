(function initTheme() {
  const saved = localStorage.getItem('gttc_lms_theme') || localStorage.getItem('gttc_theme') || 'light';
  document.documentElement.dataset.theme = saved;
})();

function setActivePage(pageId) {
  document.querySelectorAll('.page-section').forEach(section => {
    section.classList.toggle('active', section.id === `page-${pageId}`);
  });

  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === pageId);
  });

  const title = document.getElementById('topbarTitle');
  const active = document.querySelector(`.nav-item[data-page="${pageId}"] span`);
  if (title && active) title.textContent = active.textContent;

  sessionStorage.setItem('gttc_lms_page', pageId);
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('gttc_lms_theme', next);
  updateThemeButtons();
}

function updateThemeButtons() {
  const isDark = document.documentElement.dataset.theme === 'dark';
  document.querySelectorAll('.btn-theme-toggle').forEach(button => {
    button.innerHTML = isDark
      ? '<i class="ti ti-sun"></i> Light'
      : '<i class="ti ti-moon"></i> Dark';
  });
}

function getCellValue(row, key) {
  const table = row.closest('table');
  const headers = Array.from(table.querySelectorAll('thead th'));
  const index = headers.findIndex(header => header.dataset.sortKey === key);
  if (index < 0) return '';
  return row.children[index]?.textContent.trim() || '';
}

function compareValues(a, b, direction) {
  const aNum = Number(a.replace(/,/g, ''));
  const bNum = Number(b.replace(/,/g, ''));
  const bothNumbers = !Number.isNaN(aNum) && !Number.isNaN(bNum) && a !== '' && b !== '';
  const result = bothNumbers
    ? aNum - bNum
    : a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
  return direction === 'desc' ? -result : result;
}

function updateManagedTable(tableId) {
  const table = document.querySelector(`table[data-table="${tableId}"]`);
  if (!table) return;

  const search = (document.querySelector(`[data-table-search="${tableId}"]`)?.value || '').trim().toLowerCase();
  const sortKey = document.querySelector(`[data-table-sort="${tableId}"]`)?.value || '';
  const direction = document.querySelector(`[data-table-direction="${tableId}"]`)?.value || 'asc';
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr')).filter(row => !row.dataset.emptyRow);

  rows.sort((left, right) => compareValues(getCellValue(left, sortKey), getCellValue(right, sortKey), direction));
  rows.forEach(row => tbody.appendChild(row));

  let visibleCount = 0;
  rows.forEach(row => {
    const isMatch = !search || row.textContent.toLowerCase().includes(search);
    row.style.display = isMatch ? '' : 'none';
    if (isMatch) visibleCount += 1;
  });

  let emptyRow = tbody.querySelector('tr[data-empty-row="true"]');
  if (!emptyRow) {
    emptyRow = document.createElement('tr');
    emptyRow.dataset.emptyRow = 'true';
    const colSpan = table.querySelectorAll('thead th').length || 1;
    emptyRow.innerHTML = `<td colspan="${colSpan}">No matching records found.</td>`;
    tbody.appendChild(emptyRow);
  }
  emptyRow.style.display = visibleCount === 0 ? '' : 'none';

  const exportLink = document.querySelector(`[data-table-export="${tableId}"]`);
  if (exportLink) {
    const params = new URLSearchParams({ q: search, sort: sortKey, direction });
    exportLink.href = `/export/${tableId}?${params.toString()}`;
  }
}

function initManagedTables() {
  document.querySelectorAll('.managed-table[data-table]').forEach(table => {
    const tableId = table.dataset.table;
    document.querySelectorAll(`[data-table-search="${tableId}"], [data-table-sort="${tableId}"], [data-table-direction="${tableId}"]`).forEach(control => {
      control.addEventListener('input', () => updateManagedTable(tableId));
      control.addEventListener('change', () => updateManagedTable(tableId));
    });
    table.querySelectorAll('thead th[data-sort-key]').forEach(header => {
      header.addEventListener('click', () => {
        const sort = document.querySelector(`[data-table-sort="${tableId}"]`);
        const direction = document.querySelector(`[data-table-direction="${tableId}"]`);
        if (!sort || !direction) return;
        if (sort.value === header.dataset.sortKey) {
          direction.value = direction.value === 'asc' ? 'desc' : 'asc';
        } else {
          sort.value = header.dataset.sortKey;
          direction.value = 'asc';
        }
        updateManagedTable(tableId);
      });
    });
    updateManagedTable(tableId);
  });
}

function initContentFilters() {
  const tabs = document.querySelectorAll('[data-content-filter]');
  const rows = document.querySelectorAll('[data-content-group]');
  const search = document.querySelector('[data-content-search]');
  if (!tabs.length || !rows.length) return;

  const applyFilter = (group) => {
    const query = (search?.value || '').trim().toLowerCase();
    tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.contentFilter === group));
    rows.forEach(row => {
      const groupMatch = group === 'all' || row.dataset.contentGroup === group;
      const searchMatch = !query || row.textContent.toLowerCase().includes(query);
      row.style.display = groupMatch && searchMatch ? '' : 'none';
    });
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => applyFilter(tab.dataset.contentFilter));
  });

  if (search) {
    search.value = '';
    search.addEventListener('input', () => {
      const active = document.querySelector('[data-content-filter].active')?.dataset.contentFilter || 'all';
      applyFilter(active);
    });
  }

  applyFilter('all');
}

function youtubeEmbedUrl(url) {
  try {
    const normalized = /^https?:\/\//i.test(url) ? url : `https://${url}`;
    const parsed = new URL(normalized);
    if (parsed.hostname.includes('youtu.be')) {
      const id = parsed.pathname.replace('/', '').split('/')[0];
      return id ? `https://www.youtube.com/embed/${id}` : '';
    }
    if (parsed.hostname.includes('youtube.com')) {
      const id = parsed.searchParams.get('v');
      if (id) return `https://www.youtube.com/embed/${id}`;
      if (parsed.pathname.startsWith('/embed/')) return url;
      const pathParts = parsed.pathname.split('/').filter(Boolean);
      if ((pathParts[0] === 'shorts' || pathParts[0] === 'live') && pathParts[1]) {
        return `https://www.youtube.com/embed/${pathParts[1]}`;
      }
    }
  } catch (_error) {
    return '';
  }
  return '';
}

function initContentViewer() {
  const viewer = document.querySelector('[data-content-viewer]');
  if (!viewer) return;

  const title = viewer.querySelector('[data-content-viewer-title]');
  const course = viewer.querySelector('[data-content-viewer-course]');
  const type = viewer.querySelector('[data-content-viewer-type]');
  const body = viewer.querySelector('[data-content-viewer-body]');
  const frame = viewer.querySelector('[data-content-viewer-frame]');
  const previewGrid = viewer.querySelector('[data-content-preview-grid]');
  const openLink = viewer.querySelector('[data-content-viewer-open]');
  const resourceSelect = viewer.querySelector('[data-content-resource-select]');
  const close = viewer.querySelector('[data-content-viewer-close]');
  const editForm = viewer.querySelector('[data-content-edit-form]');
  const deleteForm = viewer.querySelector('[data-content-delete-form]');
  const editTitle = viewer.querySelector('[data-content-edit-title]');
  const editType = viewer.querySelector('[data-content-edit-type]');
  const editUrl = viewer.querySelector('[data-content-edit-url]');
  const editBody = viewer.querySelector('[data-content-edit-body]');

  const inferContentType = (contentType, url) => {
    const value = (url || '').toLowerCase();
    if (value.includes('youtube.com') || value.includes('youtu.be')) return 'video_link';
    if (value.endsWith('.pdf')) return 'pdf';
    if (value.endsWith('.ppt') || value.endsWith('.pptx')) return 'ppt';
    if (value.endsWith('.mp4') || value.endsWith('.mov') || value.endsWith('.webm') || value.endsWith('.mkv')) return 'video_file';
    return contentType || 'article';
  };

  const renderPreview = (contentType, url) => {
    const effectiveType = inferContentType(contentType, url);
    if (!url) {
      if (effectiveType === 'article') {
        return '<div class="content-empty">Use the Article/Text field to write lesson notes or instructions.</div>';
      }
      return '<div class="content-empty">No file or external link has been attached yet.</div>';
    }
    if (effectiveType === 'video_file') {
      return `<video controls src="${url}"></video>`;
    }
    if (effectiveType === 'video_link') {
      const embed = youtubeEmbedUrl(url);
      return embed
        ? `<iframe src="${embed}" title="Video preview" allowfullscreen></iframe>`
        : '<div class="content-empty">This video link cannot be embedded here. Use Open resource to view it.</div>';
    }
    if (effectiveType === 'pdf') {
      return `<iframe src="${url}" title="PDF preview"></iframe>`;
    }
    if (effectiveType === 'ppt') {
      return `<div class="content-empty">PPT/PPTX preview depends on browser support. Use Open resource to view or download it.</div>`;
    }
    return `<iframe src="${url}" title="Content preview"></iframe>`;
  };

  const allRows = Array.from(document.querySelectorAll('.content-row'));

  const rowKey = row => `${row.dataset.contentKind || 'lesson'}:${row.dataset.contentId || ''}`;
  const parseResources = row => {
    try {
      return JSON.parse(row.dataset.contentResources || '[]').map(resource => ({
        dataset: {
          contentId: String(resource.id || ''),
          contentKind: resource.kind || 'resource',
          contentGroup: row.dataset.contentGroup || '',
          contentTitle: resource.title || row.dataset.contentTitle || 'Untitled content',
          contentLesson: row.dataset.contentLesson || '',
          contentCourse: row.dataset.contentCourse || '',
          contentType: resource.content_type || 'article',
          contentUrl: resource.resource_url || '',
          contentBody: resource.content_body || '',
        },
      }));
    } catch (_error) {
      return [];
    }
  };

  const getLessonItems = row => {
    const resources = parseResources(row);
    return resources.length ? resources : [row];
  };

  const showContentRow = row => {
      const contentId = row.dataset.contentId;
      const contentKind = row.dataset.contentKind || 'lesson';
      const resourceUrl = row.dataset.contentUrl || '';
      title.textContent = row.dataset.contentTitle || 'Untitled content';
      course.textContent = `${row.dataset.contentCourse || ''}${row.dataset.contentLesson ? ` - ${row.dataset.contentLesson}` : ''}`;
      type.textContent = row.dataset.contentType || 'content';
      body.textContent = row.dataset.contentBody || 'No description available.';
      frame.innerHTML = renderPreview(row.dataset.contentType || '', resourceUrl);
      frame.style.display = 'none';
      openLink.href = resourceUrl || '#';
      openLink.style.display = resourceUrl ? 'inline-flex' : 'none';
      if (contentId) {
        editForm.action = `/content/update/${contentKind}/${contentId}`;
        deleteForm.action = `/content/delete/${contentKind}/${contentId}`;
      }
      editTitle.value = row.dataset.contentTitle || '';
      editType.value = row.dataset.contentType || 'article';
      editUrl.value = resourceUrl;
      editBody.value = row.dataset.contentBody || '';
      viewer.hidden = false;
      if (resourceSelect) resourceSelect.value = rowKey(row);
  };

  const populateResourceSelector = row => {
    if (!resourceSelect) return;
    const relatedRows = getLessonItems(row);
    resourceSelect.innerHTML = '';
    relatedRows.forEach(candidate => {
      const option = document.createElement('option');
      option.value = rowKey(candidate);
      option.textContent = `${candidate.dataset.contentType || 'content'} - ${candidate.dataset.contentTitle || 'Untitled content'}`;
      resourceSelect.appendChild(option);
    });
    resourceSelect.disabled = relatedRows.length <= 1;
    resourceSelect.dataset.currentCourse = row.dataset.contentCourse || '';
    resourceSelect.dataset.currentLesson = row.dataset.contentLesson || '';
    renderResourceBoxes(relatedRows, rowKey(row));
  };

  const renderResourceBoxes = (rows, activeKey) => {
    if (!previewGrid) return;
    previewGrid.innerHTML = '';
    const sections = [
      {
        title: 'YouTube / Video Link',
        empty: 'No YouTube or external video link added for this lesson yet.',
        matches: type => type === 'video_link',
      },
      {
        title: 'Uploaded Video File',
        empty: 'No uploaded video file added for this lesson yet.',
        matches: type => type === 'video_file',
      },
      {
        title: 'PDF Content',
        empty: 'No PDF uploaded for this lesson yet.',
        matches: type => type === 'pdf',
      },
      {
        title: 'PPT Content',
        empty: 'No PPT/PPTX uploaded for this lesson yet.',
        matches: type => type === 'ppt',
      },
      {
        title: 'Article / Text Content',
        empty: 'No article/text note added for this lesson yet.',
        matches: type => type === 'article',
      },
    ];

    sections.forEach(section => {
      const sectionEl = document.createElement('section');
      sectionEl.className = 'content-preview-section';
      sectionEl.innerHTML = `<h4>${section.title}</h4>`;
      const matchingRows = rows.filter(candidate =>
        section.matches(inferContentType(candidate.dataset.contentType || '', candidate.dataset.contentUrl || ''))
      );

      if (!matchingRows.length) {
        const empty = document.createElement('div');
        empty.className = 'content-preview-card content-preview-card-empty';
        empty.innerHTML = `<div class="content-empty">${section.empty}</div>`;
        sectionEl.appendChild(empty);
        previewGrid.appendChild(sectionEl);
        return;
      }

      matchingRows.forEach(candidate => {
        const resourceUrl = candidate.dataset.contentUrl || '';
        const effectiveType = inferContentType(candidate.dataset.contentType || '', resourceUrl);
        const card = document.createElement('article');
        card.className = 'content-preview-card';
        card.classList.toggle('active', rowKey(candidate) === activeKey);
        card.innerHTML = `
          <div class="content-preview-card-head">
            <div>
              <span class="badge badge-warn">${effectiveType}</span>
              <h4>${candidate.dataset.contentTitle || 'Untitled content'}</h4>
            </div>
          </div>
          <p>${candidate.dataset.contentBody || 'No description available.'}</p>
          <div class="content-preview-card-frame">${renderPreview(effectiveType, resourceUrl)}</div>
          ${resourceUrl ? `
          <a class="btn-ghost content-preview-open" href="${resourceUrl}" target="_blank" rel="noopener">
            <i class="ti ti-external-link"></i> Open resource
          </a>
          ` : ''}
        `;
        card.addEventListener('click', event => {
          if (event.target.closest('a')) return;
          showContentRow(candidate);
          renderResourceBoxes(rows, rowKey(candidate));
        });
        sectionEl.appendChild(card);
      });
      previewGrid.appendChild(sectionEl);
    });
  };

  allRows.forEach(row => {
    row.addEventListener('click', event => {
      if (event.target.closest('a')) return;
      populateResourceSelector(row);
      showContentRow(row);
      viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  resourceSelect?.addEventListener('change', () => {
    const parentRow = allRows.find(row =>
      row.dataset.contentCourse === resourceSelect.dataset.currentCourse &&
      row.dataset.contentLesson === resourceSelect.dataset.currentLesson
    );
    const relatedRows = parentRow ? getLessonItems(parentRow) : [];
    const selected = relatedRows.find(row => rowKey(row) === resourceSelect.value);
    if (selected) {
      showContentRow(selected);
      renderResourceBoxes(relatedRows, rowKey(selected));
    }
  });

  editType?.addEventListener('change', () => {
    const value = editUrl.value.trim();
    const isLocalFile = value.startsWith('/static/') || value.includes('/static/uploads/');
    const isWebUrl = /^https?:\/\//i.test(value) || /^www\./i.test(value);
    if (editType.value === 'video_link' && isLocalFile) {
      editUrl.value = '';
      editUrl.placeholder = 'Paste YouTube/video URL here';
    }
    if (['pdf', 'ppt', 'video_file'].includes(editType.value) && isWebUrl) {
      editUrl.value = '';
      editUrl.placeholder = 'Choose a file to replace this resource';
    }
  });

  deleteForm?.addEventListener('submit', event => {
    if (!confirm('Delete this content item permanently?')) {
      event.preventDefault();
    }
  });

  close?.addEventListener('click', () => {
    viewer.hidden = true;
  });
}

function initContentTypePlaceholders() {
  const placeholderByType = {
    article: {
      url: 'No link needed for article/text',
      body: 'Write the article/text content or lesson note here',
    },
    pdf: {
      url: 'Choose a PDF file to upload',
      body: 'Short PDF description or student instructions',
    },
    ppt: {
      url: 'Choose a PPT/PPTX file to upload',
      body: 'Short PPT description or student instructions',
    },
    video_link: {
      url: 'Paste YouTube/video URL here',
      body: 'Short video description or student instructions',
    },
    video_file: {
      url: 'Choose a video file to upload',
      body: 'Short uploaded video description or student instructions',
    },
  };

  document.querySelectorAll('.content-upload-form, [data-content-edit-form]').forEach(form => {
    const type = form.querySelector('select[name="content_type"]');
    const url = form.querySelector('input[name="resource_url"]');
    const body = form.querySelector('textarea[name="content_body"]');
    if (!type) return;

    const updatePlaceholders = () => {
      const copy = placeholderByType[type.value] || placeholderByType.article;
      if (url) url.placeholder = copy.url;
      if (body) body.placeholder = copy.body;
    };

    type.addEventListener('change', updatePlaceholders);
    updatePlaceholders();
  });
}

function initLessonSelect() {
  const courseSelect = document.querySelector('[data-course-select]');
  const lessonSelect = document.querySelector('[data-lesson-select]');
  const data = document.getElementById('lessonOptionsData');
  if (!courseSelect || !lessonSelect || !data) return;

  let lessonsByCourse = {};
  try {
    lessonsByCourse = JSON.parse(data.textContent || '{}');
  } catch (_error) {
    lessonsByCourse = {};
  }

  const updateLessons = () => {
    const lessons = lessonsByCourse[courseSelect.value] || [];
    lessonSelect.innerHTML = '<option value="">Select lesson / activity</option>';
    lessons.forEach(lesson => {
      const option = document.createElement('option');
      option.value = lesson.id;
      option.textContent = lesson.title;
      lessonSelect.appendChild(option);
    });
    lessonSelect.disabled = lessons.length === 0;
  };

  courseSelect.addEventListener('change', updateLessons);
  updateLessons();
}

function initAttendanceBulkForm() {
  const schoolSelect = document.querySelector('[data-attendance-school-select]');
  const batchSelect = document.querySelector('[data-attendance-batch]');
  const dateInput = document.querySelector('[data-attendance-date]');
  const rows = Array.from(document.querySelectorAll('[data-attendance-school]'));
  const empty = document.querySelector('[data-attendance-empty]');
  if (!batchSelect) return;

  let statusMap = {};
  const statusData = document.getElementById('attendanceStatusData');
  if (statusData) {
    try {
      statusMap = JSON.parse(statusData.textContent || '{}');
    } catch (_error) {
      statusMap = {};
    }
  }

  const updateExports = () => {
    const schoolId = schoolSelect?.value || '';
    const batchId = batchSelect.value || '';
    const attendanceDate = dateInput?.value || '';
    document.querySelectorAll('[data-attendance-export]').forEach(link => {
      const [scope, group] = link.dataset.attendanceExport.split('-');
      const params = new URLSearchParams({ scope, group });
      if (schoolId) params.set('school_id', schoolId);
      if (batchId) params.set('batch_id', batchId);
      if (scope === 'day') params.set('attendance_date', attendanceDate);
      link.href = `/attendance/export?${params.toString()}`;
    });
  };

  document.querySelectorAll('[data-attendance-export]').forEach(link => {
    link.addEventListener('click', event => {
      if (!batchSelect.value) {
        event.preventDefault();
        alert('Please select the batch before downloading attendance.');
      }
    });
  });

  const updateBatches = () => {
    const schoolId = schoolSelect?.value || '';
    let firstVisible = null;
    Array.from(batchSelect.options).forEach(option => {
      const isMatch = !schoolId || option.dataset.schoolId === schoolId;
      option.hidden = !isMatch;
      option.disabled = !isMatch;
      if (isMatch && !firstVisible) firstVisible = option;
    });
    if (firstVisible && batchSelect.selectedOptions[0]?.disabled) {
      batchSelect.value = firstVisible.value;
    }
    if (firstVisible && !batchSelect.value) {
      batchSelect.value = firstVisible.value;
    }
  };

  const applySavedStatuses = () => {
    const batchId = batchSelect.value || '';
    const attendanceDate = dateInput?.value || '';
    rows.forEach(row => {
      const studentId = row.dataset.attendanceStudent || '';
      const saved = statusMap[`${batchId}:${attendanceDate}:${studentId}`];
      const present = row.querySelector('input[value="present"]');
      const absent = row.querySelector('input[value="absent"]');
      if (saved === 'absent' && absent) {
        absent.checked = true;
      } else if (present) {
        present.checked = true;
      }
    });
  };

  const updateRows = () => {
    const selected = batchSelect.selectedOptions[0];
    const schoolId = selected?.dataset.schoolId || '';
    let visibleCount = 0;
    rows.forEach(row => {
      const isMatch = row.dataset.attendanceSchool === schoolId;
      row.style.display = isMatch ? '' : 'none';
      row.querySelectorAll('input').forEach(input => {
        input.disabled = !isMatch;
      });
      if (isMatch) visibleCount += 1;
    });
    if (empty) empty.style.display = visibleCount ? 'none' : '';
    applySavedStatuses();
    updateExports();
  };

  schoolSelect?.addEventListener('change', () => {
    updateBatches();
    updateRows();
  });
  batchSelect.addEventListener('change', updateRows);
  dateInput?.addEventListener('change', updateRows);
  updateBatches();
  updateRows();
}

function initReportFilters() {
  const schoolSelect = document.querySelector('[data-report-school]');
  const batchSelect = document.querySelector('[data-report-batch]');
  if (!schoolSelect || !batchSelect) return;

  const updateBatchOptions = () => {
    const schoolId = schoolSelect.value || '';
    Array.from(batchSelect.options).forEach(option => {
      if (!option.value) {
        option.hidden = false;
        option.disabled = false;
        return;
      }
      const isMatch = !schoolId || option.dataset.schoolId === schoolId;
      option.hidden = !isMatch;
      option.disabled = !isMatch;
    });
    if (batchSelect.selectedOptions[0]?.disabled) {
      batchSelect.value = '';
    }
  };

  const updateExports = () => {
    const schoolId = schoolSelect.value || '';
    const batchId = batchSelect.value || '';
    const attendanceDate = document.querySelector('[data-attendance-date]')?.value || '';
    document.querySelectorAll('[data-report-export]').forEach(link => {
      const [scope, group] = link.dataset.reportExport.split('-');
      const params = new URLSearchParams({ scope, group });
      if (schoolId) params.set('school_id', schoolId);
      if (batchId) params.set('batch_id', batchId);
      if (scope === 'day') params.set('attendance_date', attendanceDate);
      link.href = `/attendance/export?${params.toString()}`;
    });
  };

  document.querySelectorAll('[data-report-export]').forEach(link => {
    link.addEventListener('click', event => {
      if (!batchSelect.value) {
        event.preventDefault();
        alert('Please select the batch before downloading attendance.');
      }
    });
  });

  const applyFilters = () => {
    const schoolId = schoolSelect.value || '';
    const batchId = batchSelect.value || '';
    document.querySelectorAll('[data-report-row]').forEach(row => {
      const schoolMatch = !schoolId || row.dataset.schoolId === schoolId;
      const batchMatch = !batchId || row.dataset.batchId === batchId;
      row.style.display = schoolMatch && batchMatch ? '' : 'none';
    });
    document.querySelectorAll('[data-report-school-card]').forEach(card => {
      const schoolMatch = !schoolId || card.dataset.schoolId === schoolId;
      const hasVisibleRows = Array.from(card.querySelectorAll('[data-report-row]')).some(row => row.style.display !== 'none');
      card.style.display = schoolMatch && (!batchId || hasVisibleRows) ? '' : 'none';
    });
    updateExports();
  };

  schoolSelect.addEventListener('change', () => {
    updateBatchOptions();
    applyFilters();
  });
  batchSelect.addEventListener('change', applyFilters);
  document.querySelector('[data-attendance-date]')?.addEventListener('change', updateExports);
  updateBatchOptions();
  applyFilters();
}

function initGeneratedReports() {
  const filterShell = document.querySelector('[data-generated-report-filters]');
  const rows = Array.from(document.querySelectorAll('[data-generated-report-row]'));
  const detailRows = Array.from(document.querySelectorAll('[data-generated-report-detail-row]'));
  if (!filterShell || (!rows.length && !detailRows.length)) return;

  const controls = Array.from(filterShell.querySelectorAll('[data-generated-report-filter]'));
  const startDate = filterShell.querySelector('[data-generated-report-date="start"]');
  const endDate = filterShell.querySelector('[data-generated-report-date="end"]');
  const generateButton = filterShell.querySelector('[data-generate-report-button]');
  const resultMessage = document.querySelector('[data-generated-report-message]');
  const exportLinks = Array.from(document.querySelectorAll('[data-generated-report-export]'));

  const getFilters = () => {
    const filters = {};
    controls.forEach(control => {
      filters[control.dataset.generatedReportFilter] = control.value || '';
    });
    filters.startDate = startDate?.value || '';
    filters.endDate = endDate?.value || '';
    return filters;
  };

  const rowMatchesDate = (row, filters) => {
    const rowStart = row.dataset.reportStartDate || '';
    const rowEnd = row.dataset.reportEndDate || '';
    if (!filters.startDate && !filters.endDate) return true;
    if (!rowStart && !rowEnd) return true;
    if (filters.startDate && rowEnd && rowEnd < filters.startDate) return false;
    if (filters.endDate && rowStart && rowStart > filters.endDate) return false;
    return true;
  };

  const rowMatchesFilters = (row, filters) => {
    const normalize = value => String(value || '').trim().toLowerCase();
    const datasetMatches = [
      'schoolId',
      'district',
      'taluk',
      'village',
      'trainer',
      'medium',
      'gender',
      'incomeStatus',
      'physicallyChallenged',
      'urbanRural',
      'caste',
      'category',
    ].every(key => !filters[key] || normalize(row.dataset[`report${key[0].toUpperCase()}${key.slice(1)}`]) === normalize(filters[key]));
    return datasetMatches && rowMatchesDate(row, filters);
  };

  const updateExports = filters => {
    exportLinks.forEach(link => {
      const params = new URLSearchParams();
      const paramMap = {
        schoolId: 'school_id',
        district: 'district',
        taluk: 'taluk',
        village: 'village',
        trainer: 'trainer',
        medium: 'medium',
        gender: 'gender',
        incomeStatus: 'income_status',
        physicallyChallenged: 'physically_challenged',
        urbanRural: 'urban_rural',
        caste: 'caste',
        category: 'category',
      };
      Object.entries(paramMap).forEach(([filterKey, paramKey]) => {
        if (filters[filterKey]) params.set(paramKey, filters[filterKey]);
      });
      if (filters.startDate) params.set('start_date', filters.startDate);
      if (filters.endDate) params.set('end_date', filters.endDate);
      const query = params.toString();
      link.href = `/reports/export/${link.dataset.generatedReportExport}${query ? `?${query}` : ''}`;
    });
  };

  const hasActiveFilters = filters => Object.values(filters).some(value => String(value || '').trim());

  const hideGeneratedResults = () => {
    document.querySelectorAll('[data-generated-report-table]').forEach(table => {
      table.hidden = true;
    });
    if (resultMessage) resultMessage.hidden = true;
  };

  const applyFilters = () => {
    const filters = getFilters();
    hideGeneratedResults();
    updateExports(filters);
    if (!hasActiveFilters(filters)) {
      if (resultMessage) {
        resultMessage.hidden = false;
        resultMessage.textContent = 'Please select at least one report option before generating.';
        resultMessage.classList.remove('notice-success');
        resultMessage.classList.add('notice-error');
      }
      return;
    }

    let visibleTableCount = 0;
    rows.forEach(row => {
      row.style.display = rowMatchesFilters(row, filters) ? '' : 'none';
    });
    detailRows.forEach(row => {
      row.style.display = rowMatchesFilters(row, filters) ? '' : 'none';
    });

    document.querySelectorAll('[data-generated-report-table]').forEach(table => {
      const visibleSummaryRows = Array.from(table.querySelectorAll('[data-generated-report-row]')).filter(row => row.style.display !== 'none');
      const visibleDetailRows = Array.from(table.querySelectorAll('[data-generated-report-detail-row]')).filter(row => row.style.display !== 'none');
      const hasVisibleRows = visibleSummaryRows.length > 0 || visibleDetailRows.length > 0;
      table.hidden = !hasVisibleRows;
      visibleTableCount += hasVisibleRows ? 1 : 0;
      const detailCount = table.querySelector('[data-generated-detail-count]');
      if (detailCount) detailCount.textContent = String(visibleDetailRows.length);
    });

    if (resultMessage) {
      resultMessage.hidden = false;
      resultMessage.textContent = visibleTableCount
        ? 'Student report generated below. Use Download Excel to save this report.'
        : 'No matching records found for the selected filters.';
      resultMessage.classList.toggle('notice-success', visibleTableCount > 0);
      resultMessage.classList.toggle('notice-error', visibleTableCount === 0);
    }
  };

  [startDate, endDate, ...controls].forEach(control => {
    control?.addEventListener('input', hideGeneratedResults);
    control?.addEventListener('change', hideGeneratedResults);
  });
  generateButton?.addEventListener('click', applyFilters);
  updateExports(getFilters());
  hideGeneratedResults();
}

function readJsonScript(id) {
  const node = document.getElementById(id);
  if (!node) return {};
  try {
    return JSON.parse(node.textContent || '{}');
  } catch (_error) {
    return {};
  }
}

function syncBatchSelect(schoolSelect, batchSelect) {
  if (!batchSelect) return;
  const schoolId = schoolSelect?.value || '';
  Array.from(batchSelect.options).forEach(option => {
    if (!option.value) {
      option.hidden = false;
      option.disabled = false;
      return;
    }
    const isMatch = schoolId && option.dataset.schoolId === schoolId;
    option.hidden = !isMatch;
    option.disabled = !isMatch;
  });
  const selected = batchSelect.selectedOptions[0];
  if (!schoolId || !batchSelect.value || selected?.disabled || selected?.hidden) {
    batchSelect.value = '';
  }
}

function initPerformanceForms() {
  const batchForm = document.querySelector('[data-performance-batch-form]');
  const batchSchoolSelect = document.querySelector('[data-performance-school-select]');
  const batchSelect = document.querySelector('[data-performance-batch-select]');
  const batchData = readJsonScript('batchPerformanceData');

  const applyBatchAssessment = () => {
    if (!batchForm || !batchSelect) return;
    if (!batchSelect.value) {
      batchForm.querySelectorAll('[data-performance-field]').forEach(field => {
        if (field.tagName === 'SELECT') {
          field.value = 'not_assessed';
        } else if (field.name === 'remarks') {
          field.value = '';
        }
      });
      return;
    }
    const saved = batchData[batchSelect.value] || {};
    batchForm.querySelectorAll('[data-performance-field]').forEach(field => {
      const key = field.dataset.performanceField;
      if (key in saved) {
        field.value = saved[key] || '';
      } else if (field.tagName === 'SELECT') {
        field.value = 'not_assessed';
      }
    });
  };

  const updateBatchForm = () => {
    syncBatchSelect(batchSchoolSelect, batchSelect);
    applyBatchAssessment();
  };

  batchSchoolSelect?.addEventListener('change', updateBatchForm);
  batchSelect?.addEventListener('change', applyBatchAssessment);
  updateBatchForm();

  const badgeForm = document.querySelector('[data-teamwork-badge-form]');
  const badgeSchoolSelect = document.querySelector('[data-teamwork-school-select]');
  const badgeBatchSelect = document.querySelector('[data-teamwork-batch-select]');
  const badgeCourseSelect = document.querySelector('[data-teamwork-course-select]');
  const badgeData = readJsonScript('teamworkBadgeData');
  const badgeSelects = Array.from(document.querySelectorAll('[data-teamwork-badge]'));

  const updateBadgeStudents = () => {
    if (!badgeBatchSelect) return;
    if (!badgeBatchSelect.value || !badgeCourseSelect?.value) {
      badgeSelects.forEach(select => {
        select.value = '';
      });
      return;
    }
    const schoolId = badgeBatchSelect.selectedOptions[0]?.dataset.schoolId || '';
    badgeSelects.forEach(select => {
      Array.from(select.options).forEach(option => {
        if (!option.value) {
          option.hidden = false;
          option.disabled = false;
          return;
        }
        const isMatch = option.dataset.schoolId === schoolId;
        option.hidden = !isMatch;
        option.disabled = !isMatch;
      });
      const savedStudent = badgeData[`${badgeBatchSelect.value}:${badgeCourseSelect.value}:${select.dataset.teamworkBadge}`];
      select.value = savedStudent ? String(savedStudent) : '';
      if (select.selectedOptions[0]?.disabled) {
        select.value = '';
      }
    });
  };

  const updateBadgeForm = () => {
    syncBatchSelect(badgeSchoolSelect, badgeBatchSelect);
    updateBadgeStudents();
  };

  badgeSchoolSelect?.addEventListener('change', updateBadgeForm);
  badgeBatchSelect?.addEventListener('change', updateBadgeStudents);
  badgeCourseSelect?.addEventListener('change', updateBadgeStudents);
  if (badgeForm) updateBadgeForm();
}

function resetSearchFields() {
  document.querySelectorAll('input[type="search"]').forEach(input => {
    input.value = '';
  });
  sessionStorage.removeItem('gttc_lms_content_search');
  sessionStorage.removeItem('gttc_lms_content_filter');
}

function clearNoticeFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has('notice') && !url.searchParams.has('notice_kind')) return;
  url.searchParams.delete('notice');
  url.searchParams.delete('notice_kind');
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`);
}

function initAddCourseToggle() {
  const button = document.querySelector('[data-add-course-toggle]');
  const form = document.querySelector('[data-add-course-form]');
  if (!button || !form) return;

  button.addEventListener('click', () => {
    form.hidden = !form.hidden;
    button.innerHTML = form.hidden
      ? '<i class="ti ti-plus"></i> Add Course'
      : '<i class="ti ti-x"></i> Close Add Course';
  });
}

function initCourseItems() {
  const list = document.querySelector('[data-course-items]');
  const addButton = document.querySelector('[data-add-course-item]');
  const addCourseRow = () => {
    if (!list) return;
    const row = document.createElement('div');
    row.className = 'course-item-row';
    row.dataset.courseItemRow = '';
    row.innerHTML = `
      <input name="item_title" placeholder="Item title" required>
      <textarea name="item_description" placeholder="Item description"></textarea>
      <button class="btn-ghost" type="button" data-remove-course-item><i class="ti ti-trash"></i> Remove Item</button>
    `;
    row.querySelector('[data-remove-course-item]')?.addEventListener('click', () => row.remove());
    list.appendChild(row);
  };

  addButton?.addEventListener('click', addCourseRow);

  document.querySelectorAll('[data-add-manage-course-item]').forEach(button => {
    button.addEventListener('click', () => {
      const container = button.closest('.course-edit-items')?.querySelector('[data-manage-course-items]');
      if (!container) return;
      const row = document.createElement('div');
      row.className = 'course-item-row';
      row.innerHTML = `
        <input name="new_item_title" placeholder="New item title">
        <textarea name="new_item_description" placeholder="New item description"></textarea>
        <button class="btn-ghost" type="button" data-remove-course-item><i class="ti ti-trash"></i> Remove Item</button>
      `;
      row.querySelector('[data-remove-course-item]')?.addEventListener('click', () => row.remove());
      container.appendChild(row);
    });
  });
}

function initCourseSearch() {
  const search = document.querySelector('[data-course-search]');
  const cards = Array.from(document.querySelectorAll('.volume-card'));
  if (!search || !cards.length) return;

  const applySearch = () => {
    const query = search.value.trim().toLowerCase();
    const metaMatches = query
      ? new Set(cards.filter(card => {
        const terms = (card.dataset.courseMetaTerms || '')
          .split('|')
          .map(term => term.trim().toLowerCase())
          .filter(Boolean);
        return terms.some(term => term === query || term.includes(query));
      }))
      : null;

    cards.forEach(card => {
      const haystack = (card.dataset.courseSearchText || '').toLowerCase();
      const matches = !query
        || (metaMatches && metaMatches.size > 0 ? metaMatches.has(card) : haystack.includes(query));
      card.style.display = matches ? '' : 'none';
    });
  };

  search.value = '';
  search.addEventListener('input', applySearch);
  applySearch();
}

function initProfileModal() {
  const modal = document.getElementById('profileModal');
  if (!modal) return;

  const openModal = () => {
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.style.overflow = '';
  };

  document.querySelectorAll('[data-profile-open]').forEach(trigger => {
    trigger.addEventListener('click', openModal);
  });

  document.querySelectorAll('[data-profile-close]').forEach(trigger => {
    trigger.addEventListener('click', closeModal);
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !modal.hidden) {
      closeModal();
    }
  });
}

function initPasswordReveal() {
  document.querySelectorAll('[data-password-reveal]').forEach(wrapper => {
    const toggle = wrapper.querySelector('[data-password-toggle]');
    const masked = wrapper.querySelector('[data-password-masked]');
    const value = wrapper.querySelector('[data-password-value]');
    if (!toggle || !masked || !value) return;

    toggle.addEventListener('click', () => {
      const showing = !value.hidden;
      value.hidden = showing;
      masked.hidden = !showing;
      toggle.innerHTML = showing
        ? '<i class="ti ti-eye"></i> View'
        : '<i class="ti ti-eye-off"></i> Hide';
      toggle.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');
    });
  });
}

function initEnrollmentForm() {
  const form = document.querySelector('[data-enrollment-form]');
  if (!form) return;
  const schoolSelect = form.querySelector('[data-enrollment-school]');
  const batchSelect = form.querySelector('[data-enrollment-batch]');
  const studentSelect = form.querySelector('[data-enrollment-student]');
  if (!schoolSelect || !studentSelect) return;

  const syncBySchool = (selectEl) => {
    if (!selectEl) return;
    const schoolId = schoolSelect.value || '';
    Array.from(selectEl.options).forEach(option => {
      if (!option.value) {
        option.hidden = false;
        option.disabled = false;
        return;
      }
      const isMatch = schoolId && option.dataset.schoolId === schoolId;
      option.hidden = !isMatch;
      option.disabled = !isMatch;
    });
    if (!schoolId || !selectEl.value || selectEl.selectedOptions[0]?.disabled) {
      selectEl.value = '';
    }
  };

  const syncEnrollmentOptions = () => {
    syncBySchool(batchSelect);
    syncBySchool(studentSelect);
  };

  schoolSelect.addEventListener('change', syncEnrollmentOptions);
  syncEnrollmentOptions();
}

function initTableScroll() {
  document.querySelectorAll('.table-card > table').forEach(table => {
    if (table.parentElement?.classList.contains('table-scroll')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'table-scroll';
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  updateThemeButtons();
  resetSearchFields();
  clearNoticeFromUrl();

  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => setActivePage(item.dataset.page));
  });

  const date = document.getElementById('topbarDate');
  if (date) {
    date.textContent = new Date().toLocaleDateString('en-IN', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  }

  setActivePage(sessionStorage.getItem('gttc_lms_page') || 'dashboard');
  initManagedTables();
  initContentFilters();
  initContentViewer();
  initContentTypePlaceholders();
  initLessonSelect();
  initAttendanceBulkForm();
  initReportFilters();
  initGeneratedReports();
  initPerformanceForms();
  initAddCourseToggle();
  initCourseItems();
  initCourseSearch();
  initProfileModal();
  initPasswordReveal();
  initEnrollmentForm();
  initTableScroll();
});
