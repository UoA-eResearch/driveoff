<template>
    <main>
        <div class="title-section">
            <h1 class="app-title">Archive your research drive</h1>
            <h2 class="page-title">How long does your data need to be retained?</h2>
            <p>See <a class="btn-link" target="_blank" href="https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-retention">Research data retention</a> for full guidance.</p>
        </div>
        <form>
            <input name="confirm-drive" type="radio" id="rp-6y">
            <label for="rp-6y"><strong>6 years</strong><p>Suitable for all research data unless otherwise described.</p></label>
            <input name="confirm-drive" type="radio" id="rp-10y">
            <label for="rp-10y"><strong>10 years</strong><p>Suitable if the files include health data of adults, including clinical trial data, and routinely collected health data used for research.</p></label>
            <input name="confirm-drive" type="radio" id="rp-20y">
            <label for="rp-20y"><strong>20 years</strong><p>Suitable if research data are associated with registered patent.</p></label>

            <input name="confirm-drive" type="radio" id="rp-custom">
            <label for="rp-custom"><strong>Something else</strong><p>Suitable if particular ethics committee requirements, access agreements or legislative requirements apply.</p></label>
        </form>
        <section class="forward-btn">
            <RouterLink to="/confirm" class="btn btn-primary">Continue</RouterLink>
        </section>
    </main>
</template>

<style scoped>
form {
    margin-top: 1rem;
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 1rem;
    align-items:center;
}

input {
    height: 1.5rem;
    width: 1.5rem;
}

</style>