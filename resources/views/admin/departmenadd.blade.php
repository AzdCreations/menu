@extends('doctor.layouts.app')

@section('content')

    <main id="main" class="main">
        <div class="card">
            <div class="card-header">
                Be'mor
            </div>
            <div class="card-body">
                <blockquote class="blockquote mb-0">
                    <p>Siz {{\Carbon\Carbon::createFromFormat('Y-m-d', $patient->date_birth)->format('d.m.Y')}} yilda tug`ilgan {{$patient->name}} {{$patient->surname}} {{$patient->father_name}} yo`llanma beryapsiz.</p>
                    {{--                    <footer class="blockquote-footer">Someone famous in <cite title="Source Title">Source Title</cite></footer>--}}
                </blockquote>
            </div>
        </div>



        {{--        <p class="m-2">Siz {{$patient->date_birth}} yilda tug`ilgan {{$patient->name}} {{$patient->surname}} {{$patient->father_name}}ni klinik ravishda davolanish uchin yo`llanma beryapsiz.</p>--}}
        <form action="{{ route('doctor.add.store') }}" method="post">

            @csrf
            @method('post')
            <input type="hidden" name="patient_id" value="{{$patient->id}}">
            <input type="hidden" name="user_id" value="{{\Illuminate\Support\Facades\Auth::user()->id}}">
            <input type="hidden" name="money" value="0">

            <div class="form-group mb-3 mt-2">
                <select class="form-select" aria-label="Default select example">
                    <option >Bo'limni tanlang</option>
                    <option value="1">Kimyoterapiya</option>
                    <option value="2">Radioligya</option>
                    <option value="3">Patomorfologya</option>
                    <option value="3">Labaratorya</option>
                    <option value="3">Rengen diagnostika</option>
                </select>
            </div>
            <div class="form-group mb-3 mt-2">
                <label for="">Tashxisning qizqacha mazmuni</label>
                <input type="text" name="title" required placeholder="Qoyilgan tashxisning qizqacha mazmuni..." class="form-control" aria-label="Default" aria-describedby="inputGroup-sizing-default">
            </div>



            <button  class="btn btn-outline-primary">Primary</button>
        </form>
    </main>
@endsection
