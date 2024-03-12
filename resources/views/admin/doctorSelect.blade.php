@extends('doctor.layouts.app')

@section('content')


    <main id="main" class="main">
        <p style="color:#012970">
    {{\Carbon\Carbon::createFromFormat('Y-m-d', $patient->date_birth)->format('d.m.Y')}}yilda tug`ilgan {{ $patient->surname }} {{ $patient->name }} {{ $patient->father_name }}
    passport ma'lumotlari {{ $patient->passport }} {{ $patient->pnfl }} bolgan be'merni vrach  huzuriga yo'naltiring
    </p>
    <form action="{{ route('reception.doctor.select') }}" >
        <input type="text" name="id" required value="{{ $patient->id }}" hidden class="form-control" aria-label="Default">
{{--            <div class="form-group mb-3">--}}
{{--                <label for="">Passport seriasi va raqami</label>--}}
{{--                <input type="text" name="passport" required value="{{ $patient->passport }}" disabled class="form-control" aria-label="Default" aria-describedby="inputGroup-sizing-default">--}}
{{--                <input type="text" name="passport" required value="{{ $patient->passport }}" hidden class="form-control" aria-label="Default" aria-describedby="inputGroup-sizing-default">--}}
{{--            </div>--}}
{{--            <div class="form-group mb-3">--}}
{{--                <label for="">PNFL</label>--}}
{{--                <input type="text" name="pnfl" required value="{{ $patient->pnfl }}" disabled class="form-control" aria-label="Default" aria-describedby="inputGroup-sizing-default">--}}
{{--                <input type="text" name="pnfl" required value="{{ $patient->pnfl }}" hidden class="form-control" aria-label="Default" aria-describedby="inputGroup-sizing-default">--}}
{{--            </div>--}}
        <div class="form-group mb-3">
            <select class="form-select" name="doctor">
                <option value="">vrachni tanlang</option>
                @foreach($doctores as $doctor)

                    <option  value="{{ $doctor->id }}">{{ $doctor->name}}</option>

                @endforeach
            </select>
        </div>
        <button  class="btn btn-outline-primary">Primary</button>
    </form>
</main>


@endsection
