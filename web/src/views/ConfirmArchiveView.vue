<script lang="ts" setup>
import { getProjectMembers, getProjectOwners, membersToString } from '@/project';
import { formState } from '@/store';

const projectOwners = membersToString(getProjectOwners(formState.project.members));
const projectMembers = membersToString(getProjectMembers(formState.project.members));

// If the user has stated the details aren't correct, the Change links should go to the Update page. 
const projectInfoChangeLink = formState.areProjectDetailsCorrect ? "/check-details" : "/update-details"; 

</script>

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
                <td>{{  formState.project.title  }}</td>
                <td><RouterLink :to="projectInfoChangeLink">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Project description</td>
                <td> {{ formState.project.description }}</td>
                <td><RouterLink :to="projectInfoChangeLink">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Project owner</td>
                <td>{{ projectOwners }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
            </tr>
            <tr>
                <td>Project members</td>
                <td>{{ projectMembers }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
            </tr>
            <tr>
                <td>Department</td>
                <td>{{  formState.project.division }}</td>
                <td><!--<a href="#" class="btn-link">Change</a>--></td>
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
                <td>{{ formState.dataClassification }}</td>
                <td><RouterLink to="/data-classification">Change</RouterLink></td>
            </tr>
            <tr>
                <td>Retention period</td>
                <td>{{ formState.retentionPeriod }} years after today</td>
                <td><RouterLink to="/retention-period">Change</RouterLink></td>
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