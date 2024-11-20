<template>
    <h1 class="app-title">Archive your research drive</h1>
    <div class="title-section">
        <h2 class="page-title">Check your answers before sending your request</h2>
    </div>
        <h3 class="h2">Project details</h3>
    <table>
        <colgroup>
        <col class="part-name-col" />
        <col />
        <col class="change-btn-col" />
        </colgroup>
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

    <h3 class="h2">Archive details</h3>
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
    <h3 class="h2">Send this request</h3>
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

.part-name-col {
    width: 30%;
}

.change-btn-col {
    width: 20%;
}
</style>