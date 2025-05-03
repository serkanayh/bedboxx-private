// UX Improvements - Form Enhancements and Notification System

// Include these libraries in base.html
// 1. Flatpickr for date pickers: https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css and https://cdn.jsdelivr.net/npm/flatpickr
// 2. Select2 for enhanced dropdowns: https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css and https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js
// 3. Toastr for notifications: https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.css and https://cdnjs.cloudflare.com/ajax/libs/toastr.js/latest/toastr.min.js
// 4. SweetAlert2 for modals: https://cdn.jsdelivr.net/npm/sweetalert2@11

// Form Enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Initialize date pickers
    if (typeof flatpickr !== 'undefined') {
        const dateInputs = document.querySelectorAll('.date-picker');
        if (dateInputs.length > 0) {
            dateInputs.forEach(input => {
                flatpickr(input, {
                    dateFormat: "d.m.Y",
                    allowInput: true,
                    locale: {
                        firstDayOfWeek: 1,
                        weekdays: {
                            shorthand: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'],
                            longhand: ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi']
                        },
                        months: {
                            shorthand: ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'],
                            longhand: ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
                        }
                    }
                });
            });
        }

        const dateRangeInputs = document.querySelectorAll('.date-range-picker');
        if (dateRangeInputs.length > 0) {
            dateRangeInputs.forEach(input => {
                flatpickr(input, {
                    mode: "range",
                    dateFormat: "d.m.Y",
                    allowInput: true,
                    locale: {
                        firstDayOfWeek: 1,
                        weekdays: {
                            shorthand: ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'],
                            longhand: ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi']
                        },
                        months: {
                            shorthand: ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'],
                            longhand: ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
                        }
                    }
                });
            });
        }
    }

    // Initialize enhanced select dropdowns
    if (typeof $.fn.select2 !== 'undefined') {
        const selectInputs = document.querySelectorAll('.select2-enable');
        if (selectInputs.length > 0) {
            $(selectInputs).select2({
                theme: 'bootstrap-5',
                width: '100%',
                placeholder: 'Seçiniz...',
                allowClear: true
            });
        }
    }

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    if (forms.length > 0) {
        Array.from(forms).forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                    
                    // Show validation messages
                    const invalidInputs = form.querySelectorAll(':invalid');
                    invalidInputs.forEach(input => {
                        // Create custom validation message
                        const feedback = input.nextElementSibling;
                        if (feedback && feedback.classList.contains('invalid-feedback')) {
                            if (input.validity.valueMissing) {
                                feedback.textContent = 'Bu alan zorunludur.';
                            } else if (input.validity.typeMismatch) {
                                feedback.textContent = 'Lütfen geçerli bir değer girin.';
                            } else if (input.validity.patternMismatch) {
                                feedback.textContent = 'Lütfen istenen formatta girin.';
                            }
                        }
                        
                        // Scroll to first invalid input
                        if (input === invalidInputs[0]) {
                            input.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            input.focus();
                        }
                    });
                }
                
                form.classList.add('was-validated');
            }, false);
        });
    }

    // Autocomplete for hotel names
    const hotelInputs = document.querySelectorAll('.hotel-autocomplete');
    if (hotelInputs.length > 0 && typeof $.fn.autocomplete !== 'undefined') {
        hotelInputs.forEach(input => {
            $(input).autocomplete({
                source: function(request, response) {
                    $.ajax({
                        url: "/api/hotels/autocomplete/",
                        dataType: "json",
                        data: {
                            term: request.term
                        },
                        success: function(data) {
                            response(data);
                        }
                    });
                },
                minLength: 2,
                select: function(event, ui) {
                    // If there's a hidden input for hotel ID, update it
                    const hotelIdInput = document.getElementById(input.dataset.idTarget);
                    if (hotelIdInput) {
                        hotelIdInput.value = ui.item.id;
                    }
                }
            });
        });
    }

    // AJAX form submissions
    const ajaxForms = document.querySelectorAll('.ajax-form');
    if (ajaxForms.length > 0) {
        ajaxForms.forEach(form => {
            form.addEventListener('submit', function(event) {
                event.preventDefault();
                
                // Show loading indicator
                const submitBtn = form.querySelector('[type="submit"]');
                const originalBtnText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> İşleniyor...';
                
                // Get form data
                const formData = new FormData(form);
                
                // Send AJAX request
                fetch(form.action, {
                    method: form.method,
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': getCookie('csrftoken')
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    // Reset form
                    form.reset();
                    form.classList.remove('was-validated');
                    
                    // Show success message
                    if (typeof toastr !== 'undefined') {
                        toastr.success(data.message || 'İşlem başarıyla tamamlandı.');
                    }
                    
                    // If there's a redirect URL, navigate to it
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    }
                    
                    // If there's a callback function, call it
                    if (form.dataset.callback) {
                        window[form.dataset.callback](data);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    if (typeof toastr !== 'undefined') {
                        toastr.error('Bir hata oluştu. Lütfen tekrar deneyin.');
                    }
                })
                .finally(() => {
                    // Reset button
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                });
            });
        });
    }
});

// Notification System
// Initialize Toastr
if (typeof toastr !== 'undefined') {
    toastr.options = {
        closeButton: true,
        debug: false,
        newestOnTop: true,
        progressBar: true,
        positionClass: "toast-top-right",
        preventDuplicates: false,
        onclick: null,
        showDuration: "300",
        hideDuration: "1000",
        timeOut: "5000",
        extendedTimeOut: "1000",
        showEasing: "swing",
        hideEasing: "linear",
        showMethod: "fadeIn",
        hideMethod: "fadeOut"
    };
}

// Function to show confirmation dialog
function showConfirmDialog(title, text, confirmButtonText, cancelButtonText, callback) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: title,
            text: text,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3f51b5',
            cancelButtonColor: '#f44336',
            confirmButtonText: confirmButtonText || 'Evet',
            cancelButtonText: cancelButtonText || 'İptal'
        }).then((result) => {
            if (result.isConfirmed && typeof callback === 'function') {
                callback();
            }
        });
    } else {
        // Fallback to browser confirm
        if (confirm(text)) {
            if (typeof callback === 'function') {
                callback();
            }
        }
    }
}

// Function to show success message
function showSuccessMessage(title, text) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: title,
            text: text,
            icon: 'success',
            confirmButtonColor: '#3f51b5'
        });
    } else if (typeof toastr !== 'undefined') {
        toastr.success(text, title);
    } else {
        alert(title + ': ' + text);
    }
}

// Function to show error message
function showErrorMessage(title, text) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: title,
            text: text,
            icon: 'error',
            confirmButtonColor: '#3f51b5'
        });
    } else if (typeof toastr !== 'undefined') {
        toastr.error(text, title);
    } else {
        alert(title + ': ' + text);
    }
}

// Function to show loading indicator
function showLoading(text) {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            title: text || 'İşleniyor...',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
    }
}

// Function to hide loading indicator
function hideLoading() {
    if (typeof Swal !== 'undefined') {
        Swal.close();
    }
}

// Helper function to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Back to top button
document.addEventListener('DOMContentLoaded', function() {
    // Create back to top button
    const backToTopBtn = document.createElement('button');
    backToTopBtn.id = 'back-to-top';
    backToTopBtn.innerHTML = '<i class="bi bi-arrow-up"></i>';
    backToTopBtn.setAttribute('title', 'Sayfa Başına Dön');
    backToTopBtn.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #3f51b5;
        color: white;
        border: none;
        display: none;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(backToTopBtn);
    
    // Show/hide button based on scroll position
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopBtn.style.display = 'flex';
        } else {
            backToTopBtn.style.display = 'none';
        }
    });
    
    // Scroll to top when button is clicked
    backToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
});
