<template>
    <h1 class="app-title">Archive your research drive</h1>
    <h2 class="page-title">Check and update drive details</h2>
    <p>These project and drive details are records we hold from when the drive was initially created.</p>
    <table>
        <tbody>
            <tr>
                <td>Project name</td>
                <td>Tītoki metabolomics</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project description</td>
                <td> Stress in plants could be defined as any change in growth condition(s) that disrupts metabolic homeostasis and requires an adjustment of metabolic pathways in a process that is usually referred to as acclimation. Metabolomics could contribute significantly to the study of stress biology in plants and other organisms by identifying different compounds, such as by-products of stress metabolism, stress signal transduction molecules or molecules that are part of the acclimation response of plants. </td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project owner</td>
                <td>Samina Nicholas</td>
                <td><a href="#" class="btn-link">Change</a></td>
            </tr>
            <tr>
                <td>Project members</td>
                <td>Zach Luther, Jarrod Hossam, Melisa Edric</td>
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