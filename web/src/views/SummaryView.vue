<script lang="ts">
import { RouterLink } from 'vue-router';

</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <h2 class="page-title">Is this the drive you want to archive?</h2>
        <section class="drive-details-card">
            <h3 class="drive-name">reslig-202200001-Tītoki-metabolomics</h3>
            <p class="storage-size">5120GB</p>
            <!-- <table>
                <tbody>
                    <tr>
                        <td>
                            Capacity
                        </td>
                        <td>
                            5120GB
                        </td>
                    </tr>
                    <tr>
                        <td>
                            For project
                        </td>
                        <td>
                            Tītoki metabolomics
                        </td>
                    </tr>
                    <tr>
                        <td>
                            Project owners
                        </td>
                        <td>
                            Samina Nicholas
                        </td>
                    </tr>
                    <tr>
                        <td>
                            Ended on
                        </td>
                        <td>
                            31 January 2025
                        </td>
                    </tr>
                </tbody>
            </table> -->
            <a href="#" class="btn-link">See files in drive...</a>
        </section>
        <form>
            <input name="confirm-drive" type="radio" id="yes-drive">
            <label for="yes-drive"><strong>Yes, it is.</strong></label>
            <input name="confirm-drive" type="radio" id="no-drive">
            <label for="no-drive"><strong>No, it's not.</strong></label>
        </form>
        <section class="forward-btn">
            <RouterLink to="/update-details" class="btn btn-primary">Continue</RouterLink>
        </section>
    </main>
</template>

<style scoped>
td {
    padding: 0.5rem;
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

.drive-details-card {
    border: 1px solid lightgray;
    border-left: 6px solid #0080a7;
    padding-left: 1rem;
    padding: 1rem;
    margin: 2rem 0;
}

.drive-name {
    font-size: 1.3rem;
    font-weight: bold;
}


</style>