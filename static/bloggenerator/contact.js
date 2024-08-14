document.addEventListener('DOMContentLoaded', () => {
    const contactForm = document.getElementById('contact-form');
    const responseMessage = document.getElementById('response-message');

    contactForm.addEventListener('submit', (event) => {
        event.preventDefault();

        // Simulate form submission
        const formData = new FormData(contactForm);
        const name = formData.get('name');
        const email = formData.get('email');
        const message = formData.get('message');

        // Simple form validation
        if (name && email && message) {
            responseMessage.textContent = `Thank you, ${name}! Your message has been sent.`;
            responseMessage.style.color = 'green';
            contactForm.reset();
        } else {
            responseMessage.textContent = 'Please fill out all fields.';
            responseMessage.style.color = 'red';
        }
    });
});
