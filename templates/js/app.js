// mock data
export const mockAuthors = [
    {
        id: 1,
        name: "Dr. Sarah Chen",
        institution: "Department of Computer Science",
        publicationCount: 127,
        orcid: "0000-0002-1234-5678",
        subInstitution: "Computer Science"
    },
    {
        id: 2,
        name: "Prof. Michael Rodriguez",
        institution: "Institute of Advanced Materials",
        publicationCount: 203,
        orcid: "0000-0003-8765-4321",
        subInstitution: "Materials Science"
    },
    {
        id: 3,
        name: "Dr. Emily Nakamura",
        institution: "Center for Biomedical Research",
        publicationCount: 89,
        orcid: "0000-0001-9876-5432",
        subInstitution: "Biomedical Sciences"
    },
    {
        id: 4,
        name: "Prof. James O'Brien",
        institution: "Department of Physics",
        publicationCount: 156,
        orcid: "0000-0004-5678-1234",
        subInstitution: "Physics"
    },
    {
        id: 5,
        name: "Dr. Aisha Patel",
        institution: "School of Engineering",
        publicationCount: 94,
        orcid: "0000-0005-2345-6789",
        subInstitution: "Engineering"
    },
    {
        id: 6,
        name: "Prof. David Kim",
        institution: "Department of Mathematics",
        publicationCount: 178,
        orcid: "0000-0006-3456-7890",
        subInstitution: "Mathematics"
    },
    {
        id: 7,
        name: "Dr. Maria Santos",
        institution: "Center for Climate Research",
        publicationCount: 112,
        orcid: "0000-0007-4567-8901",
        subInstitution: "Environmental Science"
    },
    {
        id: 8,
        name: "Prof. Robert Johnson",
        institution: "Department of Chemistry",
        publicationCount: 189,
        orcid: "0000-0008-5678-9012",
        subInstitution: "Chemistry"
    }
];

export const mockPublications = [
    {
        doi: "10.1007/s40815-024-01754-8",
        title: "Novel Interval Type-2 ANFIS Modeling Based on One-Step Type Reducer Algorithm",
        authors: "Adrián Alberto-Rodríguez, Virgilio López-Morales, & Julio Cesar Ramos-Fernández",
        year: 2025
    },
    {
        doi: "10.1109/RITA.2025.3627590",
        title: "Experimental Study of Ludoeducational Robotics to Teaching of a Second Language",
        authors: "Eduardo Vázquez Bonilla, Anilú Franco-Árcega, Virgilio López-Morales, & Manuel Alejandro Ojeda-Misses",
        year: 2025
    },
    {
        doi: "10.3390/info9120300",
        title: "Multiple Criteria Decision-Making in Heterogeneous Groups of Management Experts",
        authors: "Virgilio López-Morales",
        year: 2024
    }
];

export const mockKeywords = [
    'Machine Learning', 'Quantum Computing', 'Climate Science',
    'Biomedical Engineering', 'Artificial Intelligence', 'Data Analysis',
    'Network Analysis', 'Computational Biology', 'Materials Science',
    'Renewable Energy', 'Nanotechnology', 'Robotics',
    'Cybersecurity', 'Blockchain', 'Cloud Computing', 'IoT Systems'
];

export const mockInstitutes = [
    'Instituto de Artes',
    'Instituto de Ciencias Agropecuarias',
    'Instituto de Ciencias Básicas e Ingeniería',
    'Instituto de Ciencias de la Salud',
    'Instituto de Ciencias Económico Administrativas',
    'Instituto de Ciencias Sociales y Humanidades',
    'Escuela Superior de Actopan',
    'Escuela Superior de Apan',
    'Escuela Superior de Atotonilco de Tula',
    'Escuela Superior de Ciudad Sahagún',
    'Escuela Superior de Huejutla',
    'Escuela Superior de Tepeji del Río',
    'Escuela Superior de Tizayuca',
    'Escuela Superior de Tlahuelilpan',
    'Escuela Superior de Zimapán'
];

export const mockSubInstitutionStats = {
    "Instituto de Ciencias Sociales y Humanidades": 49,
    "Instituto de Ciencias Básicas e Ingeniería": 38,
    "Instituto de Ciencias de la Salud": 41,
    "Escuela Superior de Tizayuca": 36,
    "Escuela Superior de Tlahuelilpan": 44,
    "Escuela Superior de Zimapán": 39
};

export const mockYearlyPublications = {
    2018: 234,
    2019: 289,
    2020: 312,
    2021: 398,
    2022: 445,
    2023: 512,
    2024: 428
};

export const mockPublicationTypes = {
    "Journal Article": 1245,
    "Conference Paper": 678,
    "Book Chapter": 234,
    "Thesis": 89,
    "Preprint": 156,
    "Review": 123
};

// state
let currentSearchMode = 'authors';
let currentFilters = [];
let yearFilter = { from: null, to: null };
let selectedKeywords = [];
let selectedInstitutes = [];
let charts = {};

// init
export function initApp() {
    setupEventListeners();
    updateSearchMode('authors');
    renderAuthorResults(mockAuthors);

    document.getElementById('yearFrom').value = '2020';
    document.getElementById('yearTo').value = '2025';
}

// functions
function setupEventListeners() {
    const searchModeBtn = document.getElementById('searchModeBtn');
    const searchModeMenu = document.getElementById('searchModeMenu');

    searchModeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        searchModeBtn.classList.toggle('active');
        searchModeMenu.classList.toggle('active');
    });

    document.addEventListener('click', () => {
        searchModeBtn.classList.remove('active');
        searchModeMenu.classList.remove('active');
    });

    document.querySelectorAll('.search-mode-option').forEach(option => {
        option.addEventListener('click', (e) => {
            e.stopPropagation();
            updateSearchMode(option.dataset.mode);
        });
    });
}

function updateSearchMode(mode) {
    currentSearchMode = mode;

    if (mode === 'authors') {
        renderAuthorResults(mockAuthors);
    } else if (mode === 'works') {
        renderWorkResults(mockPublications);
    }
}

function renderAuthorResults(authors) {
    const resultsList = document.getElementById('resultsList');
    const resultsCount = document.getElementById('resultsCount');

    resultsCount.textContent = authors.length.toLocaleString();

    resultsList.innerHTML = authors.map(author => `
        <div class="result-card">
            <h3>${author.name}</h3>
            <p>${author.institution}</p>
            <p>${author.publicationCount} publications</p>
        </div>
    `).join('');
}

function renderWorkResults(works) {
    const resultsList = document.getElementById('resultsList');
    const resultsCount = document.getElementById('resultsCount');

    resultsCount.textContent = works.length.toLocaleString();

    resultsList.innerHTML = works.map(work => `
        <div class="result-card">
            <h3>${work.title}</h3>
            <p>${work.authors}</p>
            <p>${work.year}</p>
        </div>
    `).join('');
}

// util
function debounce(func, wait) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}