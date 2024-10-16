<template>
    <h1 class="app-title">Archive your research drive</h1>
    <h2 class="page-title">Check and update drive details</h2>
    <p>These project and drive details are records we hold from when the drive was initially created.</p>
    <table>
        <tbody>
            <tr>
                <td>Project name</td>
                <td>Kawakawa metabolomics</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project description</td>
                <td> Kawakawa (Piper excelsum) is an endemic New Zealand plant with a long history of cultural and medicinal use amongst Mori. Kawakawa aqueous extracts are reported to contain a significant number of chemical compounds of different class. Some of these have been reported to influence nutrient uptake and other physiological activities such as inflammation and related pathways. However, not much is known about the possible toxicity and biological activity of its metabolites in humans. We have performed clinical studies to investigate the Bioavailability of kawakawa metabolites and the mechanisms of human metabolism upon ingestion of kawakawa tea. Metabolomic analysis of tea, urine, and plasma was performed using Orbitrap-LC-MS/MS analysis. Data analysis was carried out to interpret the mass spectrometric data. </td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project owner</td>
                <td>Chris Pook</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project members</td>
                <td>Ramya Jayaprakash, Kalita Prangnell, Nick Young</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Department</td>
                <td>Liggins Institute</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
        </tbody>
    </table>
    <section class="forward-btn">
            <RouterLink to="/data-classification" class="btn btn-primary">Save and continue</RouterLink>
        </section>
</template>

<style scoped>
td {
    padding: 0.5rem;
    border-bottom: 1px solid gray;
    /* background-color: lightgray; */
    
}
td:first-child {
    font-family: NationalBold;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
}
</style>