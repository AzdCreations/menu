@extends('admin.layouts.app')

@section('content')


    <!-- ======= Header ======= -->


    <!-- ======= Sidebar ======= -->


    <main id="main" class="main">
        @if (\Session::has('success'))
            <div class="alert alert-success">
                <ul>
                    <li>{!! \Session::get('success') !!}</li>
                </ul>
            </div>
        @endif
        <div class="pagetitle">
            <h1>Dashboard</h1>

{{--            <div class="btn-add">--}}
{{--                <a href="{{ route('patient.create') }}">Be`mor qoshish</a>--}}
{{--            </div>--}}

        </div><!-- End Page Title -->

        <section class="section dashboard">
            <div class="row">


                <div class="col-12 table_one">
                    <div class="card recent-sales overflow-auto table_one">

                        <div class="filter">
                            <a class="icon" href="#" data-bs-toggle="dropdown"><i class="bi bi-three-dots"></i></a>
                            <ul class="dropdown-menu dropdown-menu-end dropdown-menu-arrow">
                                <li class="dropdown-header text-start">
                                    <h6>Filter</h6>
                                </li>

                                <li><a class="dropdown-item" href="#">Today</a></li>
                                <li><a class="dropdown-item" href="#">This Month</a></li>
                                <li><a class="dropdown-item" href="#">This Year</a></li>
                            </ul>
                        </div>

                        <div class="card-body">
                            <h5 class="card-title">Recent Sales <span>| Today</span></h5>

                            <table class="table table-borderless datatable">
                                <thead>
                                <tr>
{{--                                    <th scope="col">#</th>--}}
                                    <th scope="col">F.I.O'</th>
                                    <th scope="col">Tug`ilgan yili</th>
                                    <th scope="col">Jinsi</th>
                                    <th scope="col" colspan="2"></th>

                                </tr>
                                </thead>
                                <tbody>

{{--                                @foreach($patients as $patient)--}}
{{--                                    <tr>--}}
{{--                                        <th scope="row"><a href="#">{{$patient -> id }}</a></th>--}}
{{--                                        <td>{{$patient -> name }} {{$patient -> surname }} {{$patient -> father_name }}</td>--}}
{{--                                        <td>{{$patient -> date_birth }}</a></td>--}}
{{--                                        <td>{{$patient -> gd[$patient->gender] }}</td>--}}
{{--                                        <td>  <a class="btn btn-warning btn-sm" href="{{ route('doctor.add.diagnosis',$patient -> id ) }}"><i class="fa-solid fa-hospital m-2"></i> Klinik davolanish</a>--}}
{{--                                        <a class="btn btn-warning btn-sm" href="{{ route('doctor.add.department',$patient -> id ) }}"><i class="fa fa-reply m-2" aria-hidden="true"></i> boshqa bo`limga yuborish</a></td>--}}
{{--                                    </tr>--}}
{{--                                @endforeach--}}

                                </tbody>
                            </table>

                        </div>

                    </div>
                </div>




            </div>
        </section>

    </main><!-- End #main -->

    <!-- ======= Footer ======= -->


    {{--<a href="#" class="back-to-top d-flex align-items-center justify-content-center"><i class="bi bi-arrow-up-short"></i></a>--}}

    <!-- Vendor JS Files -->





@endsection
