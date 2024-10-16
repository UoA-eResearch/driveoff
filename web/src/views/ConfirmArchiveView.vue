<template>
    <h1 class="app-title">Archive your research drive</h1>
    <h2 class="page-title">Check your answers before sending your request</h2>
    <h3>Project details</h3>
    <table>
        <colgroup>
        <col class="part-name-col" />
        <col />
        <col class="change-btn-col" />
        </colgroup>
        <tbody>
            <tr>
                <td>Project name</td>
                <td>Kawakawa metabolomics</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project description</td>
                <td> Kawakawa (Piper excelsum) is an endemic New Zealand plant with a long history of cultural and medicinal use amongst Māori. Kawakawa aqueous extracts are reported to contain a significant number of chemical compounds of different class. Some of these have been reported to influence nutrient uptake and other physiological activities such as inflammation and related pathways. However, not much is known about the possible toxicity and biological activity of its metabolites in humans. We have performed clinical studies to investigate the Bioavailability of kawakawa metabolites and the mechanisms of human metabolism upon ingestion of kawakawa tea. Metabolomic analysis of tea, urine, and plasma was performed using Orbitrap-LC-MS/MS analysis. Data analysis was carried out to interpret the mass spectrometric data. </td>
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

    <h3>Archive details</h3>
    <table>
        <colgroup>
        <col class="part-name-col" />
        <col />
        <col class="change-btn-col" />
        </colgroup>
        <tbody>
            <tr>
                <td>Data classification</td>
                <td>Sensitive</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Retention period</td>
                <td>6 years</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
        </tbody>
    </table>
    <h3>Send this request</h3>
    By sending this request you are confirming that the details are correct and you wish to archive this drive.
    <section class="forward-btn">
            <RouterLink to="/finish" class="btn btn-primary">Submit</RouterLink>
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

td:last-of-type {
    text-align: end;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
    margin-bottom: 2rem;
    table-layout: fixed;;
}

h3 {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
    font-family: NationalBold, sans-serif;

}

.part-name-col {
    width: 30%;
}

.change-btn-col {
    width: 20%;
}
</style>